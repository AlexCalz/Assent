"""Ownership graph — "derive, don't demand" resolution.

Implements the population strategy from ``docs/graph-strategy.md``: resolve
``system -> owner`` for the *one* system a change is about to touch, at propose-time,
from a cheapest-to-richest source ladder, with confidence-scored edges that carry
provenance. Corroboration across tiers raises confidence; staleness decays it. An
incomplete graph degrades to an *unknown* owner (confidence 0.0) so the policy engine
escalates rather than guessing an approver — coverage gaps cost latency, not safety.

This is deterministic backend code, same posture as the policy engine: no LLM in the
resolution path. (Tier-5 document extraction, which *is* LLM-driven and untrusted,
would produce ``OwnershipClaim`` rows upstream; it can only ever add a claim, never
lower a gate — see the docstring on ``Source.DOCS``.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from assent.change import Owner


class Source(str, Enum):
    """The source ladder, cheapest/richest first. ``tier`` is the ladder rank (1 = best,
    machine-readable, zero human effort); ``base_confidence`` is how much we trust a
    fresh claim from this source; ``half_life_days`` is how fast that trust decays as the
    claim goes stale.
    """

    CODE = "code"          # CODEOWNERS, git blame, Terraform/Pulumi, K8s labels
    OPS = "ops"            # PagerDuty, Opsgenie, Backstage/OpsLevel, Slack owners
    CLOUD = "cloud"        # resource tags, CMDB (ServiceNow), EDR inventory
    IDENTITY = "identity"  # IAM policies, group membership
    DOCS = "docs"          # runbooks/wikis/postmortems -> LLM extraction. UNTRUSTED.
    HUMAN = "human"        # a human confirmed/corrected this edge in a prior approval

    @property
    def tier(self) -> int:
        return {
            "code": 1, "ops": 2, "cloud": 3, "identity": 4, "docs": 5, "human": 6,
        }[self.value]

    @property
    def base_confidence(self) -> float:
        # Machine-readable, versioned sources are trusted more than extracted prose.
        # Human confirmation is the strongest single signal.
        return {
            "human": 0.98,
            "code": 0.90,
            "ops": 0.80,
            "cloud": 0.65,
            "identity": 0.60,
            "docs": 0.40,
        }[self.value]

    @property
    def half_life_days(self) -> float:
        # How long until a fresh claim's confidence halves. Code/IaC rarely goes stale;
        # ops rotations and doc contents go stale fast.
        return {
            "code": 365.0,
            "human": 180.0,
            "identity": 120.0,
            "cloud": 90.0,
            "ops": 45.0,
            "docs": 30.0,
        }[self.value]


@dataclass(frozen=True)
class OwnershipClaim:
    """One edge asserting who owns a system, with provenance. The atom the graph is
    built from; every human approval adds or corrects one of these (the flywheel)."""

    system: str
    owner_id: str
    source: Source
    observed_at: datetime
    # Optional per-claim override of the source's default trust (e.g. a weak CODEOWNERS
    # wildcard match vs. an exact one). Defaults to the source's base confidence.
    strength: Optional[float] = None

    def base(self) -> float:
        return self.source.base_confidence if self.strength is None else self.strength

    def decayed_confidence(self, now: datetime) -> float:
        """Confidence after staleness decay: ``base * 0.5 ** (age / half_life)``."""
        age_days = max(0.0, (now - self.observed_at).total_seconds() / 86400.0)
        return self.base() * (0.5 ** (age_days / self.source.half_life_days))


def _noisy_or(confidences: List[float]) -> float:
    """Combine independent corroborating signals: ``1 - prod(1 - c)``. Two sources that
    agree raise confidence above either alone; this is how corroboration works."""
    product = 1.0
    for c in confidences:
        product *= (1.0 - max(0.0, min(1.0, c)))
    return 1.0 - product


@dataclass
class OwnershipGraph:
    """A confidence-scored, provenance-carrying store of ownership claims.

    ``resolve`` is the JIT per-change lookup: gather claims for one system, decay by
    staleness, corroborate agreeing sources, and return the winning ``Owner`` (or an
    unknown owner if the graph has nothing / only stale-to-nothing claims)."""

    _claims: Dict[str, List[OwnershipClaim]] = field(default_factory=dict)

    def add(self, claim: OwnershipClaim) -> "OwnershipGraph":
        self._claims.setdefault(claim.system, []).append(claim)
        return self

    def record_human_confirmation(
        self, system: str, owner_id: str, now: Optional[datetime] = None
    ) -> "OwnershipGraph":
        """The flywheel: every approval confirms or corrects an edge. A human-sourced
        claim is the strongest signal and refreshes the system's ownership."""
        return self.add(
            OwnershipClaim(system, owner_id, Source.HUMAN, now or _utcnow())
        )

    def resolve(self, system: str, now: Optional[datetime] = None) -> Owner:
        now = now or _utcnow()
        claims = self._claims.get(system, [])
        if not claims:
            # Nothing known. Degrade to "ask a human" — the engine will escalate.
            return Owner(id="unknown", source="none", confidence=0.0)

        # Decay each claim, then group by candidate owner and corroborate within a group.
        by_owner: Dict[str, List[OwnershipClaim]] = {}
        decayed: Dict[str, List[float]] = {}
        for claim in claims:
            c = claim.decayed_confidence(now)
            if c <= 0.0:
                continue
            by_owner.setdefault(claim.owner_id, []).append(claim)
            decayed.setdefault(claim.owner_id, []).append(c)

        if not decayed:
            return Owner(id="unknown", source="stale", confidence=0.0)

        # Pick the owner with the strongest corroborated confidence. Ties break toward
        # the claim from the best (lowest-tier-number) source.
        def score(owner_id: str) -> tuple[float, int]:
            combined = _noisy_or(decayed[owner_id])
            best_tier = min(cl.source.tier for cl in by_owner[owner_id])
            return (combined, -best_tier)

        winner = max(decayed, key=score)
        combined = _noisy_or(decayed[winner])
        best_source = min(by_owner[winner], key=lambda cl: cl.source.tier).source

        # Provenance string: name the strongest source, note corroboration count.
        n = len(by_owner[winner])
        provenance = best_source.value if n == 1 else f"{best_source.value}+{n - 1}"
        return Owner(id=winner, source=provenance, confidence=round(combined, 4))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
