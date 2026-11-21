"""Campaign correlation — grouping rapid-fire signals into coordinated attacks.

ARTEX and similar agentic attack frameworks operate at machine speed: 27 events
in 23 seconds, recon-to-exfil in 15 minutes, 2,900 sign-in attempts per minute.
Individual signals lose meaning at that velocity. What matters is the *campaign*:
a set of related signals that together reveal a coordinated attacker.

The correlator groups signals by target, time window, and attack-chain adjacency.
When enough related signals arrive fast enough, it promotes the campaign to a
higher urgency tier — which tightens the gate on every constituent signal. A
campaign that spans multiple systems (lateral movement) automatically widens the
blast radius, which the policy engine already handles: wider blast → no auto.

Two safety properties:

* The correlator never *lowers* risk. It can widen blast radius and raise caution,
  but it cannot shrink an envelope or bypass a gate.
* Campaign membership is recorded in the ledger, so the "why was this escalated"
  answer traces back to the correlated signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from assent.proposer import Signal


@dataclass(frozen=True)
class CampaignSignal:
    """A signal annotated with its campaign context."""

    signal: Signal
    campaign_id: Optional[str]
    campaign_size: int = 1
    campaign_targets: frozenset = frozenset()
    velocity: float = 0.0  # signals per minute in this campaign


ATTACK_CHAIN: Dict[str, Set[str]] = {
    "credential_spray_burst": {"agentic_recon_burst", "cloud_identity_pivot", "kerberos_attack"},
    "agentic_recon_burst": {"lateral_movement_burst", "privilege_escalation", "kerberos_attack"},
    "cloud_identity_pivot": {"oauth_app_abuse", "privilege_escalation", "supply_chain_pivot"},
    "oauth_app_abuse": {"privilege_escalation", "cloud_identity_pivot", "supply_chain_pivot"},
    "kerberos_attack": {"lateral_movement_burst", "privilege_escalation", "agentic_recon_burst"},
    "lateral_movement_burst": {"webshell_deployment", "exfil_staging", "privilege_escalation"},
    "privilege_escalation": {"exfil_staging", "lateral_movement_burst"},
    "webshell_deployment": {"exfil_staging", "lateral_movement_burst", "c2_beacon"},
    "supply_chain_pivot": {"agentic_recon_burst", "cloud_identity_pivot", "privilege_escalation"},
    "exfil_staging": set(),
    "c2_beacon": {"lateral_movement_burst", "agentic_recon_burst", "exfil_staging"},
    "compromised_session": {"agentic_recon_burst", "cloud_identity_pivot", "privilege_escalation"},
    "leaked_credential": {"credential_spray_burst", "cloud_identity_pivot"},
}


@dataclass
class _Campaign:
    id: str
    signals: List[Signal] = field(default_factory=list)
    targets: Set[str] = field(default_factory=set)
    kinds: Set[str] = field(default_factory=set)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class CampaignCorrelator:
    """Groups signals into campaigns based on temporal proximity and attack-chain adjacency.

    A new signal joins an existing campaign if:
    - It arrives within ``window`` of the campaign's last signal, AND
    - Its kind is chain-adjacent to a kind already in the campaign, OR
      its target overlaps with the campaign's targets.

    Otherwise it starts a new campaign.
    """

    def __init__(self, window: timedelta = timedelta(minutes=10)) -> None:
        self.window = window
        self._campaigns: Dict[str, _Campaign] = {}
        self._next_id = 1

    def correlate(self, signal: Signal, now: Optional[datetime] = None) -> CampaignSignal:
        now = now or datetime.now(timezone.utc)
        match = self._find_campaign(signal, now)

        if match is None:
            cid = f"campaign-{self._next_id:04d}"
            self._next_id += 1
            match = _Campaign(id=cid)
            self._campaigns[cid] = match

        match.signals.append(signal)
        match.targets.add(signal.target)
        match.kinds.add(signal.kind)
        if match.first_seen is None:
            match.first_seen = now
        match.last_seen = now

        elapsed = (now - match.first_seen).total_seconds()
        velocity = len(match.signals) / max(elapsed / 60.0, 1 / 60.0)

        return CampaignSignal(
            signal=signal,
            campaign_id=match.id,
            campaign_size=len(match.signals),
            campaign_targets=frozenset(match.targets),
            velocity=round(velocity, 2),
        )

    def get_campaign(self, campaign_id: str) -> Optional[_Campaign]:
        return self._campaigns.get(campaign_id)

    def active_campaigns(self, now: Optional[datetime] = None) -> List[_Campaign]:
        now = now or datetime.now(timezone.utc)
        return [
            c for c in self._campaigns.values()
            if c.last_seen is not None and (now - c.last_seen) < self.window
        ]

    def _find_campaign(self, signal: Signal, now: datetime) -> Optional[_Campaign]:
        best: Optional[_Campaign] = None
        best_score = 0

        for c in self._campaigns.values():
            if c.last_seen is None or (now - c.last_seen) >= self.window:
                continue

            score = 0
            if signal.target in c.targets:
                score += 2
            adjacent = ATTACK_CHAIN.get(signal.kind, set())
            if adjacent & c.kinds:
                score += 3
            reverse_adjacent = {
                k for k, v in ATTACK_CHAIN.items() if signal.kind in v
            }
            if reverse_adjacent & c.kinds:
                score += 3
            if signal.kind in c.kinds:
                score += 1

            if score > 0 and score > best_score:
                best = c
                best_score = score

        return best

    @staticmethod
    def campaign_blast_radius(campaign: _Campaign) -> int:
        return len(campaign.targets)

    @staticmethod
    def is_multi_stage(campaign: _Campaign) -> bool:
        return len(campaign.kinds) >= 2
