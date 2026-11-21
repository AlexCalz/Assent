"""Tests for the campaign correlator — grouping agentic attack signals."""

from datetime import datetime, timedelta, timezone

import pytest

from assent.campaign import CampaignCorrelator, CampaignSignal, ATTACK_CHAIN
from assent.proposer import Signal


def _signal(kind: str, target: str = "sys-a") -> Signal:
    return Signal(kind=kind, target=target, summary="test")


NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestCampaignCorrelation:
    def test_single_signal_starts_campaign(self):
        c = CampaignCorrelator()
        cs = c.correlate(_signal("agentic_recon_burst"), now=NOW)
        assert cs.campaign_id is not None
        assert cs.campaign_size == 1

    def test_related_signals_join_same_campaign(self):
        c = CampaignCorrelator()
        cs1 = c.correlate(_signal("credential_spray_burst", "ad-tenant"), now=NOW)
        cs2 = c.correlate(
            _signal("agentic_recon_burst", "ad-tenant"),
            now=NOW + timedelta(seconds=30),
        )
        assert cs1.campaign_id == cs2.campaign_id
        assert cs2.campaign_size == 2

    def test_chain_adjacent_signals_correlate(self):
        c = CampaignCorrelator()
        # First two signals share a target so they form a campaign
        cs1 = c.correlate(_signal("credential_spray_burst", "sys-a"), now=NOW)
        # kerberos_attack is chain-adjacent to credential_spray_burst AND shares target
        cs2 = c.correlate(
            _signal("kerberos_attack", "sys-a"),
            now=NOW + timedelta(seconds=10),
        )
        assert cs1.campaign_id == cs2.campaign_id

    def test_unrelated_signals_separate_campaigns(self):
        c = CampaignCorrelator()
        cs1 = c.correlate(_signal("exfil_staging", "sys-a"), now=NOW)
        # malicious_domain on a different target, not chain-adjacent
        cs2 = c.correlate(
            _signal("malicious_domain", "sys-z"),
            now=NOW + timedelta(seconds=5),
        )
        assert cs1.campaign_id != cs2.campaign_id

    def test_window_expiry_starts_new_campaign(self):
        c = CampaignCorrelator(window=timedelta(minutes=5))
        cs1 = c.correlate(_signal("agentic_recon_burst"), now=NOW)
        cs2 = c.correlate(
            _signal("lateral_movement_burst"),
            now=NOW + timedelta(minutes=10),
        )
        assert cs1.campaign_id != cs2.campaign_id

    def test_campaign_blast_radius_is_target_count(self):
        c = CampaignCorrelator()
        # All signals share sys-a as a target so they join the same campaign,
        # then additional targets widen the blast radius
        c.correlate(_signal("credential_spray_burst", "sys-a"), now=NOW)
        c.correlate(
            _signal("kerberos_attack", "sys-a"), now=NOW + timedelta(seconds=5)
        )
        # This one hits a new target but is chain-adjacent + same campaign
        c.correlate(
            _signal("lateral_movement_burst", "sys-a"),
            now=NOW + timedelta(seconds=10),
        )
        campaigns = c.active_campaigns(NOW + timedelta(seconds=10))
        assert len(campaigns) == 1
        # Only 1 unique target here, but let's verify blast_radius = target count
        assert c.campaign_blast_radius(campaigns[0]) == 1

        # Now add signals that spread to new targets
        c2 = CampaignCorrelator()
        c2.correlate(_signal("credential_spray_burst", "sys-a"), now=NOW)
        c2.correlate(
            _signal("lateral_movement_burst", "sys-a"),
            now=NOW + timedelta(seconds=5),
        )
        c2.correlate(
            _signal("webshell_deployment", "sys-b"),
            now=NOW + timedelta(seconds=8),
        )
        campaigns2 = c2.active_campaigns(NOW + timedelta(seconds=8))
        multi_target = [c for c in campaigns2 if len(c.targets) > 1]
        assert len(multi_target) == 1
        assert c2.campaign_blast_radius(multi_target[0]) == 2

    def test_multi_stage_detection(self):
        c = CampaignCorrelator()
        c.correlate(_signal("credential_spray_burst"), now=NOW)
        c.correlate(
            _signal("kerberos_attack"), now=NOW + timedelta(seconds=5)
        )
        campaigns = c.active_campaigns(NOW + timedelta(seconds=5))
        assert c.is_multi_stage(campaigns[0])

    def test_single_kind_not_multi_stage(self):
        c = CampaignCorrelator()
        c.correlate(_signal("credential_spray_burst", "sys-a"), now=NOW)
        c.correlate(
            _signal("credential_spray_burst", "sys-b"),
            now=NOW + timedelta(seconds=5),
        )
        campaigns = c.active_campaigns(NOW + timedelta(seconds=5))
        assert not c.is_multi_stage(campaigns[0])

    def test_velocity_reflects_signals_per_minute(self):
        c = CampaignCorrelator()
        c.correlate(_signal("credential_spray_burst", "sys-a"), now=NOW)
        c.correlate(
            _signal("kerberos_attack", "sys-a"),
            now=NOW + timedelta(seconds=2),
        )
        cs3 = c.correlate(
            _signal("lateral_movement_burst", "sys-a"),
            now=NOW + timedelta(seconds=4),
        )
        # 3 signals in 4 seconds = 45/minute
        assert cs3.velocity == pytest.approx(45.0, abs=1.0)

    def test_attack_chain_is_symmetric_coverage(self):
        """Every kind that appears as a value also appears as a key."""
        all_values = set()
        for v in ATTACK_CHAIN.values():
            all_values |= v
        for kind in all_values:
            assert kind in ATTACK_CHAIN, f"{kind} appears as adjacent but has no entry"


class TestArtexPlaybooks:
    """Verify the new ARTEX signal kinds produce valid proposals."""

    @pytest.fixture
    def runtime(self):
        from assent import Assent, Inventory, SystemRecord, Environment
        inv = Inventory()
        inv.add(SystemRecord("target-sys", Environment.PROD, tier0=True, dependents=10))
        return Assent(inventory=inv)

    @pytest.mark.parametrize("kind", [
        "agentic_recon_burst",
        "oauth_app_abuse",
        "credential_spray_burst",
        "cloud_identity_pivot",
        "exfil_staging",
        "kerberos_attack",
        "supply_chain_pivot",
        "lateral_movement_burst",
        "privilege_escalation",
        "webshell_deployment",
    ])
    def test_artex_signal_produces_decision(self, runtime, kind):
        signal = Signal(kind=kind, target="target-sys", summary="test")
        record = runtime.submit(signal)
        assert record.decision is not None
        # Prod + tier-0 should never auto-execute
        assert record.state.value != "auto_executed"

    def test_artex_campaign_escalates(self, runtime):
        """A multi-signal campaign should escalate due to widened blast radius."""
        from datetime import datetime, timedelta, timezone
        t = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
        r1 = runtime.submit(
            Signal(kind="credential_spray_burst", target="target-sys"), now=t
        )
        r2 = runtime.submit(
            Signal(kind="kerberos_attack", target="target-sys"),
            now=t + timedelta(seconds=5),
        )
        # Both should be escalated (prod + tier-0)
        assert r1.state.value == "escalated"
        assert r2.state.value == "escalated"
