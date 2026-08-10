"""The deterministic policy engine — the trust decision, in code.

This is step 5 of the pipeline in ``docs/policy-engine.md``: a pure function mapping
``(risk_envelope, owner)`` — plus the catalog and rollback facts carried on the
``Change`` — to ``{auto | route-to-owner | escalate}``. It is deterministic on
purpose: the trust decision "must be code: auditable, testable, versioned."

The invariant (D6) is enforced structurally here, not by convention:

* Every gate-*opening* check reads a measured fact (catalog, environment, blast radius,
  reversibility, ownership graph). None reads model confidence.
* ``confidence`` and ``context_caution`` are consulted only in the *downgrade* pass,
  which can move a decision toward ``ESCALATE`` but never toward ``AUTO``.

So auto-execution is earned by a **low risk envelope**, never by **high confidence** —
the sharp break from "99% confidence => act."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from assent.catalog import ActionCatalog, DEFAULT_CATALOG
from assent.change import Change, Environment, Reversibility


class Decision(str, Enum):
    """The three terminal gates. Ordered from most to least autonomous so that a
    downgrade is always a move to a later member."""

    AUTO = "auto"                      # measured envelope is low enough to auto-execute
    ROUTE_TO_OWNER = "route_to_owner"  # gate, sent to the authoritative owner
    ESCALATE = "escalate"              # gate, broadened — no confident owner / fail-safe

    @property
    def rank(self) -> int:
        return {"auto": 0, "route_to_owner": 1, "escalate": 2}[self.value]


@dataclass(frozen=True)
class PolicyResult:
    """The engine's output: the decision plus the audit trail of why."""

    decision: Decision
    reasons: List[str] = field(default_factory=list)

    def with_decision(self, decision: Decision, reason: str) -> "PolicyResult":
        return PolicyResult(decision=decision, reasons=[*self.reasons, reason])


@dataclass(frozen=True)
class AutonomyPolicy:
    """The per-customer *dial*. Autonomy is earned, so the defaults are conservative:
    no auto-execution in prod, only reversible actions, tight blast radius, and a
    confidence floor below which we always escalate.

    None of these fields can *open* a gate the measured facts have closed — they only
    make the AUTO bar harder to clear.
    """

    allow_auto_writes: bool = True             # master switch for any write autonomy
    auto_environments: frozenset = frozenset({Environment.DEV, Environment.STAGING})
    max_auto_blast_radius: int = 5             # narrow only
    allow_auto_tier0: bool = False             # crown-jewel targets never auto
    min_owner_confidence: float = 0.75         # below => cannot silently route
    min_confidence_for_auto: float = 0.85      # confidence can only tighten, never open


class PolicyEngine:
    """Deterministic gating. Construct once per policy version; ``evaluate`` is pure."""

    def __init__(
        self,
        catalog: ActionCatalog = DEFAULT_CATALOG,
        autonomy: AutonomyPolicy = AutonomyPolicy(),
    ) -> None:
        self.catalog = catalog
        self.autonomy = autonomy

    def evaluate(self, change: Change) -> PolicyResult:
        env = change.risk_envelope
        action = change.action
        reasons: List[str] = []

        # --- Step 1: catalog is the safety boundary. Unknown => fail safe to human. ---
        action_class = self.catalog.get(action.type)
        if action_class is None:
            return PolicyResult(
                Decision.ESCALATE,
                [f"action '{action.type}' is not in the catalog; failing safe to human"],
            )

        # --- Step 2: reads are autonomous. The real trust boundary is read vs write. ---
        if not action.is_write:
            return PolicyResult(Decision.AUTO, ["read-only action; reads are autonomous"])

        # From here down we are gating a *write*. Decide whether the measured facts
        # permit AUTO. Any single failure closes the AUTO door; we then choose between
        # ROUTE_TO_OWNER and ESCALATE based on ownership confidence.

        auto_blocked: List[str] = []

        if not self.autonomy.allow_auto_writes:
            auto_blocked.append("write autonomy is disabled for this customer")

        # A write with no rollback plan can never auto-execute. "No undo => no autonomy."
        if not change.has_rollback:
            auto_blocked.append("no rollback plan; a write without undo never auto-executes")

        # Reversibility is measured from the catalog *and* the concrete envelope; take
        # the more conservative of the two.
        effective_reversibility = _most_conservative(
            action_class.reversibility, env.reversibility
        )
        if effective_reversibility is not Reversibility.REVERSIBLE:
            auto_blocked.append(
                f"reversibility is '{effective_reversibility.value}'; only reversible "
                f"writes auto-execute"
            )

        if env.environment not in self.autonomy.auto_environments:
            auto_blocked.append(
                f"environment '{env.environment.value}' is outside the auto set"
            )

        if env.hits_tier0 and not self.autonomy.allow_auto_tier0:
            auto_blocked.append("target is tier-0; tier-0 writes never auto-execute")

        if env.blast_radius > self.autonomy.max_auto_blast_radius:
            auto_blocked.append(
                f"blast_radius {env.blast_radius} exceeds auto ceiling "
                f"{self.autonomy.max_auto_blast_radius}"
            )

        if auto_blocked:
            # Measured facts closed the AUTO door. Route if we trust the owner, else escalate.
            return self._gate(change, reasons=auto_blocked)

        # --- Downgrade pass: model-supplied signals may only TIGHTEN, never open. ---
        # At this point the measured envelope permits AUTO. Confidence and context can
        # still push us to a human, but nothing here could have opened a closed gate.
        if env.confidence < self.autonomy.min_confidence_for_auto:
            return self._gate(
                change,
                reasons=[
                    f"confidence {env.confidence:.2f} below auto floor "
                    f"{self.autonomy.min_confidence_for_auto:.2f}; confidence only tightens"
                ],
            )

        if change.context_caution:
            return self._gate(
                change,
                reasons=["doc-grounded caution flag raised; context tightens, never opens"],
            )

        return PolicyResult(
            Decision.AUTO,
            [
                "reversible + narrow + in-scope environment with a rollback plan and "
                "sufficient confidence; low risk envelope earns auto-execution"
            ],
        )

    def _gate(self, change: Change, reasons: List[str]) -> PolicyResult:
        """AUTO is off the table; choose the human path.

        A confident owner gets the change routed straight to them. An unknown or
        low-confidence owner is never silently routed — it escalates (broadens),
        because a stale/guessed owner is a dangerous approver.
        """
        owner = change.owner
        if owner.known and owner.confidence >= self.autonomy.min_owner_confidence:
            return PolicyResult(
                Decision.ROUTE_TO_OWNER,
                [*reasons, f"routing to owner '{owner.id}' (confidence {owner.confidence:.2f})"],
            )
        return PolicyResult(
            Decision.ESCALATE,
            [
                *reasons,
                "owner unknown or below routing-confidence floor; escalating rather than "
                "guessing an approver",
            ],
        )


def _most_conservative(a: Reversibility, b: Reversibility) -> Reversibility:
    """Return the more conservative (less reversible) of two classifications."""
    order = {
        Reversibility.REVERSIBLE: 0,
        Reversibility.RECOVERABLE: 1,
        Reversibility.IRREVERSIBLE: 2,
    }
    return a if order[a] >= order[b] else b
