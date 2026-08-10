"""Proposal — turning a detection signal into a typed, gated-ready ``Change``.

This is step 1–2 of the pipeline in ``docs/policy-engine.md``: diagnose and propose
(the LLM's job — reasoning over novel situations) followed by **deterministic**
normalization to a catalog action ``{type, target, params}``. An action that doesn't
normalize to a known catalog type is not proposed at all; it becomes an escalation.

Two safety properties are structural here, not conventions:

* **Untrusted data is never an instruction.** A ``Signal`` is typed data. Its free-text
  fields (``summary``, indicator values) are carried for human display and are never
  parsed for commands — the action is chosen by a rule keyed on ``kind``, not by
  interpreting attacker-influenced text.
* **The proposer never measures its own risk.** ``environment``, ``blast_radius`` and
  ``tier0`` come from the ``Inventory``; ``reversibility`` comes from the catalog. The
  proposer supplies only its ``confidence`` — the one axis that can only tighten.

``RuleBasedProposer`` is the deterministic reference. An LLM-backed proposer implements
the same ``Proposer`` protocol and is constrained identically: it may pick the action
type and confidence, and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Protocol, runtime_checkable

from assent.catalog import ActionCatalog, DEFAULT_CATALOG
from assent.change import Action, Change, Owner, RiskEnvelope
from assent.inventory import Inventory


@dataclass(frozen=True)
class Signal:
    """An incoming detection. Untrusted input: data to reason about, never a command."""

    kind: str                                   # typed detection class, e.g. "c2_beacon"
    target: str                                 # the system the detection concerns
    summary: str = ""                           # human-readable; display only
    indicators: Mapping[str, str] = field(default_factory=dict)
    source: str = "unknown"                     # which sensor reported it
    severity: str = "medium"                    # threat severity (NOT risk-to-act)


@dataclass(frozen=True)
class Proposal:
    """The proposer's output: either a change to gate, or a refusal with a reason."""

    change: Optional[Change]
    refusal: str = ""

    @property
    def proposed(self) -> bool:
        return self.change is not None


@runtime_checkable
class Proposer(Protocol):
    """Anything that can turn a signal into a proposed change."""

    def propose(self, signal: Signal) -> Proposal: ...


@dataclass(frozen=True)
class _Playbook:
    """A signal kind mapped to the catalog action that responds to it."""

    action_type: str
    confidence: float
    rationale: str


# The response map. Deliberately small and explicit: an unmapped signal kind produces no
# proposal, which the runtime turns into an escalation rather than a guess.
DEFAULT_PLAYBOOKS: Dict[str, _Playbook] = {
    "malicious_domain": _Playbook(
        "block_domain", 0.94,
        "Domain matches a known-malicious indicator; blocking egress is the containment.",
    ),
    "c2_beacon": _Playbook(
        "quarantine_host", 0.88,
        "Host shows command-and-control beaconing; isolating it contains the spread.",
    ),
    "leaked_credential": _Playbook(
        "rotate_credential", 0.91,
        "Credential observed outside the trust boundary; rotation invalidates it.",
    ),
    "overprivileged_role": _Playbook(
        "revoke_iam_role", 0.82,
        "Role grants access well beyond its use; revoking restores least privilege.",
    ),
    "compromised_session": _Playbook(
        "disable_user_session", 0.90,
        "Session shows takeover indicators; revoking forces re-authentication.",
    ),
}


class RuleBasedProposer:
    """Deterministic reference proposer.

    Chooses an action from the playbook map, then builds the risk envelope entirely
    from *measured* sources: the inventory (environment, blast radius, tier-0) and the
    catalog (reversibility). It contributes only the confidence.
    """

    def __init__(
        self,
        inventory: Inventory,
        catalog: ActionCatalog = DEFAULT_CATALOG,
        playbooks: Optional[Dict[str, _Playbook]] = None,
    ) -> None:
        self.inventory = inventory
        self.catalog = catalog
        self.playbooks = dict(playbooks or DEFAULT_PLAYBOOKS)

    def propose(self, signal: Signal) -> Proposal:
        playbook = self.playbooks.get(signal.kind)
        if playbook is None:
            return Proposal(
                None, f"no playbook for signal kind '{signal.kind}'; needs a human"
            )

        action_class = self.catalog.get(playbook.action_type)
        if action_class is None:
            # Normalization failed: the playbook names an action the catalog can't
            # classify. Fail safe rather than proposing an unclassifiable action.
            return Proposal(
                None,
                f"action '{playbook.action_type}' is not in the catalog; needs a human",
            )

        system = self.inventory.get(signal.target)

        envelope = RiskEnvelope(
            blast_radius=system.blast_radius,          # measured
            reversibility=action_class.reversibility,  # measured (catalog)
            environment=system.environment,            # measured
            confidence=playbook.confidence,            # proposer's only contribution
            hits_tier0=system.tier0,                   # measured
        )

        return Proposal(
            Change(
                action=Action(
                    type=playbook.action_type,
                    target=signal.target,
                    is_write=action_class.is_write,
                    params=dict(signal.indicators),
                ),
                risk_envelope=envelope,
                # Owner is resolved by the runtime from the ownership graph; the
                # proposer must not invent one.
                owner=Owner(id="unknown", source="unresolved", confidence=0.0),
                reasoning=playbook.rationale,
                rollback=_rollback_plan(playbook.action_type, signal.target),
            )
        )


def _rollback_plan(action_type: str, target: str) -> Optional[str]:
    """The undo plan per action type. No plan => the engine withholds autonomy."""
    plans = {
        "block_domain": f"Remove {target} from the egress blocklist.",
        "quarantine_host": f"Release {target} from network isolation.",
        "disable_user_session": f"Restore normal session issuance for {target}.",
        "rotate_credential": f"Re-issue the previous credential version for {target}.",
        "revoke_iam_role": f"Re-grant the removed role binding on {target}.",
    }
    return plans.get(action_type)
