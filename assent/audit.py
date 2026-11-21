"""The independent audit agent — a first-class safety property.

``docs/objectives.md`` makes the audit agent non-negotiable: "a second opinion on the
risk envelope from a system with no stake in the action. Acting-vs-audit disagreement
is itself an escalation trigger." ``docs/policy-engine.md`` sharpens it: the auditor
computes its *own* confidence read, and divergence beyond a threshold from the acting
agent is a **deterministic** escalation.

Two things live here:

* ``AuditOpinion`` / ``AuditAgent`` — the interface. In production the auditor is
  LLM-driven, but crucially it is a *separate* system with no stake in the action.
* ``RuleBasedAuditor`` — a deterministic reference auditor that derives an independent
  confidence purely from measured facts. It never reads the acting agent's confidence,
  so its number is a genuine second opinion, not an echo.

The *decision* about what to do with a divergence is not here — it is in the policy
engine, where it belongs (deterministic, auditable). Per the invariant, the audit read
can only ever *tighten* the gate: it escalates on disagreement and lowers the effective
confidence, but it can never open a gate the measured facts have closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from assent.catalog import ActionCatalog, DEFAULT_CATALOG
from assent.change import Change, Environment, Reversibility


@dataclass(frozen=True)
class AuditOpinion:
    """A second opinion on a proposed change.

    ``confidence`` is the auditor's *independent* read that the change is safe to act on
    (0.0..1.0). ``dissent`` is an explicit objection that escalates regardless of the
    numbers — the auditor saw something disqualifying (e.g. an action it cannot classify).
    """

    confidence: float
    rationale: str = ""
    dissent: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("audit confidence must be in [0.0, 1.0]")


@runtime_checkable
class AuditAgent(Protocol):
    """Anything that can independently review a change. Kept as a protocol so an
    LLM-backed auditor and the deterministic reference auditor are interchangeable."""

    def review(self, change: Change) -> AuditOpinion: ...


class RuleBasedAuditor:
    """A deterministic second opinion derived only from measured facts.

    It deliberately does **not** look at ``change.risk_envelope.confidence`` — that is
    the acting agent's number, and echoing it would defeat the point of an independent
    check. Instead it starts optimistic and applies multiplicative penalties for each
    property that makes an action riskier to take, and dissents outright when it cannot
    reason about the action at all.
    """

    def __init__(self, catalog: ActionCatalog = DEFAULT_CATALOG) -> None:
        self.catalog = catalog

    def review(self, change: Change) -> AuditOpinion:
        action = change.action
        env = change.risk_envelope

        if not action.is_write:
            return AuditOpinion(1.0, "read-only; no state change to audit")

        # An action the auditor's catalog can't classify is a hard dissent: it cannot
        # vouch for something it doesn't understand.
        if not self.catalog.knows(action.type):
            return AuditOpinion(
                0.0, f"action '{action.type}' is unknown to the auditor", dissent=True
            )

        # Start from full confidence and apply a penalty per risk factor. Calibrated so
        # a genuinely low-risk write (reversible, narrow, non-prod) still clears the
        # engine's auto floor when the auditor agrees — otherwise autonomy is impossible.
        confidence = 1.0
        notes = []

        if env.environment is Environment.PROD:
            confidence *= 0.55
            notes.append("prod target")
        elif env.environment is Environment.STAGING:
            confidence *= 0.97

        if env.hits_tier0:
            confidence *= 0.5
            notes.append("tier-0 system")

        rev_factor = {
            Reversibility.REVERSIBLE: 1.0,
            Reversibility.RECOVERABLE: 0.8,
            Reversibility.IRREVERSIBLE: 0.3,
        }[env.reversibility]
        confidence *= rev_factor
        if env.reversibility is not Reversibility.REVERSIBLE:
            notes.append(f"{env.reversibility.value} action")

        # Wider blast radius erodes confidence smoothly (a single-system change is barely
        # touched; a broad one is heavily penalized).
        confidence *= 1.0 / (1.0 + env.blast_radius / 20.0)
        if env.blast_radius > 5:
            notes.append(f"blast radius {env.blast_radius}")

        if not change.has_rollback:
            confidence *= 0.3
            notes.append("no rollback plan")

        if change.context_caution:
            confidence *= 0.7
            notes.append("doc-grounded caution")

        rationale = "; ".join(notes) if notes else "no risk factors flagged"
        # A collapsed confidence is itself a dissent — the auditor won't vouch for it.
        return AuditOpinion(round(confidence, 4), rationale, dissent=confidence < 0.2)
