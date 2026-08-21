"""Tests for Trident-inspired Assent surfaces: agents, packages, dashboard, demo inject."""

from assent.agents import AgentStatus, roster_for
from assent.app import demo_app, inject_demo_scenario, render_ledger, render_queue
from assent.dashboard import render_change, render_mission, render_overview
from assent.package import build_package


def test_agent_roster_reflects_live_runtime():
    app = demo_app()
    agents = roster_for(app)
    assert len(agents) == 4
    names = {a.name for a in agents}
    assert "Acting Proposer" in names
    assert "Independent Auditor" in names
    assert "Policy Engine" in names
    assert all(a.status in AgentStatus for a in agents)


def test_incident_package_carries_trident_surfaces_without_relaxing_gate():
    app = demo_app()
    record = next(r for r in app.records() if r.change is not None)
    pkg = build_package(record)
    assert pkg.record_id == record.id
    assert pkg.executive_summary
    assert pkg.attack_timeline
    assert "confidence never authorizes" in pkg.executive_summary.lower() or \
           "Confidence is" in pkg.executive_summary
    # confidence is present for display but package does not invent a looser gate
    assert pkg.gate_reasons == list(record.reasons)
    d = pkg.to_dict()
    assert "mitre_techniques" in d and "agent_trace" in d


def test_triage_package_for_unmapped_signal():
    app = demo_app()
    triage = next(r for r in app.records() if r.change is None)
    pkg = build_package(triage)
    assert pkg.decision == "triage"
    assert pkg.confidence == 0.0
    assert "no playbook" in pkg.executive_summary.lower() or "ask-a-human" in pkg.executive_summary.lower()


def test_mission_dashboard_renders_chat_shell():
    app = demo_app()
    page = render_mission(app, actor="alex", profile="cloud")
    assert "Assent" in page
    assert "Alerts" in page
    assert "Approvals" in page
    assert "Infrastructure" in page
    assert "Jordan" in page
    assert "Simulate alert" in page
    assert "Cloud · Personal" in page
    assert "acting as" in page


def test_private_profile_label():
    app = demo_app()
    page = render_mission(app, actor="alex", profile="private")
    assert "Private Tenant · Agency" in page
    assert "SSO" in page


def test_overview_lists_inventory():
    app = demo_app()
    page = render_overview(app, actor="alex", profile="cloud")
    assert "payments-api" in page
    assert "Infrastructure" in page
    assert "pt-canvas" in page
    assert "Acting Proposer" in page


def test_change_package_page():
    app = demo_app()
    record = app.queue()[0]
    page = render_change(app, record, actor="alex", profile="cloud")
    assert record.id in page
    assert "Executive summary" in page
    assert "Agent reasoning trace" in page
    assert "Gated remediation" in page


def test_approvals_split_you_vs_jordan():
    from assent.dashboard import render_app

    app = demo_app()
    you = render_app(app, actor="you", profile="cloud", tool="approvals")
    jordan = render_app(app, actor="jordan", profile="cloud", tool="approvals")
    assert "Desk of <strong>You</strong>" in you
    assert "Desk of <strong>Jordan Hale</strong>" in jordan
    assert "payments-api" in jordan or "payments-latency" in jordan


def test_demo_inject_adds_signals():
    app = demo_app()
    before = app.stats()["total"]
    inject_demo_scenario(app)
    assert app.stats()["total"] == before + 3


def test_legacy_render_helpers_still_work():
    app = demo_app()
    q = render_queue(app, "alex")
    led = render_ledger(app, "alex")
    assert "Assent" in q and "chain verified" in led
