"""Assent — the deterministic core of the gating engine.

This package is the reference implementation of the moat described in the concept
docs (see ``docs/policy-engine.md`` and decision **D2**/**D6**): the ``Change``
primitive and the deterministic ``PolicyEngine`` that maps a measured risk envelope
plus an authoritative owner to a gating decision.

The whole package is intentionally free of LLM calls and third-party dependencies.
Per the invariant (D6), *nothing that could relax the gate lives here as a model
opinion* — every gate-opening property is measured, and this code is the part that
must be "auditable, testable, versioned."
"""

from assent.change import (
    Action,
    Change,
    Environment,
    Owner,
    Reversibility,
    RiskEnvelope,
)
from assent.catalog import ActionCatalog, ActionClass, DEFAULT_CATALOG
from assent.graph import OwnershipClaim, OwnershipGraph, Source
from assent.policy import Decision, PolicyEngine, PolicyResult

__all__ = [
    "Action",
    "ActionCatalog",
    "ActionClass",
    "Change",
    "DEFAULT_CATALOG",
    "Decision",
    "Environment",
    "Owner",
    "OwnershipClaim",
    "OwnershipGraph",
    "PolicyEngine",
    "PolicyResult",
    "Reversibility",
    "RiskEnvelope",
    "Source",
]

__version__ = "0.1.0"
