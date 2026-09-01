"""The ``Change`` primitive and the pieces of its risk envelope.

Everything the product reasons about reduces to one object (decision **D2**):

    Change {
      action:        exact command + target
      reasoning:     why — grounded in internal docs (LLM-produced narrative)
      risk_envelope: blast_radius x reversibility x environment x confidence
      owner:         who is authoritative for the affected stack
      rollback:      the undo plan
    }

The types here carry the *measured* facts. The LLM's job (diagnose, propose, narrate,
and emit a confidence) happens upstream; by the time a ``Change`` reaches the policy
engine the only model-supplied number is ``confidence`` — and per D6 that number can
only ever *tighten* the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


class Environment(str, Enum):
    """Where the action lands. A gate-opening property, so it is measured from the
    target's metadata, never inferred by the model."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Reversibility(str, Enum):
    """How cleanly an action can be undone.

    Pre-classified per action *type* in the catalog (block-domain = reversible,
    delete-volume = irreversible). This can open the gate, so it is measured from the
    action catalog, not opined by the model.
    """

    REVERSIBLE = "reversible"          # clean, automated undo (e.g. re-allow a domain)
    RECOVERABLE = "recoverable"        # undo possible but with cost/latency (restore from backup)
    IRREVERSIBLE = "irreversible"      # no undo (delete volume, rotate-and-destroy)


@dataclass(frozen=True)
class Owner:
    """The authoritative owner of the affected stack, resolved from the ownership
    graph. ``confidence`` reflects corroboration/staleness of the graph edge, not the
    model — low-confidence or missing ownership must degrade to "ask a human."
    """

    id: str
    source: str = "unknown"            # which tier of the source ladder produced this
    confidence: float = 0.0            # 0.0..1.0, from graph edge corroboration

    @property
    def known(self) -> bool:
        return bool(self.id) and self.id != "unknown"


@dataclass(frozen=True)
class Action:
    """A typed, catalog-normalized action. ``type`` must exist in the action catalog;
    an uncatalogued action fails safe to human (see ``policy.py``)."""

    type: str                          # catalog key, e.g. "block_domain"
    target: str                        # the concrete resource acted on
    is_write: bool                     # reads are autonomous; writes gate
    params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskEnvelope:
    """The four measured axes that decide *risk-to-act* (not threat severity).

    Three of the four are measured facts that can open the gate. ``confidence`` is the
    single model-supplied axis and, by invariant, can only raise caution.
    """

    blast_radius: int                  # count of systems/users affected (0 = none)
    reversibility: Reversibility
    environment: Environment
    confidence: float                  # 0.0..1.0, LLM-produced, audit-cross-checked
    hits_tier0: bool = False           # target is a tier-0 / crown-jewel system

    def __post_init__(self) -> None:
        if self.blast_radius < 0:
            raise ValueError("blast_radius must be >= 0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")


@dataclass(frozen=True)
class Change:
    """A proposed change: the unit the policy engine gates."""

    action: Action
    risk_envelope: RiskEnvelope
    owner: Owner
    reasoning: str = ""                # LLM narrative; explains, never decides
    rollback: Optional[str] = None     # the undo plan; None => no autonomy, ever
    context_caution: bool = False      # doc-grounded caution flag; can only tighten

    @property
    def has_rollback(self) -> bool:
        return bool(self.rollback)
