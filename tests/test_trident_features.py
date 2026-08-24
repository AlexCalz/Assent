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
    assert "Simulate alert" in page
    assert "Security Operations Lead" in page
    assert "select class=\"profile\"" not in page
    assert "wordmark\">Assent" in page or ">Assent</span>" in page
    assert 'class="state"' not in page
    assert "imp-critical" not in page
    assert "thread-row" in page


def test_agents_are_labelled_as_agents_people_get_job_titles():
    app = demo_app()
    record = next(r for r in app.queue() if r.change is not None)
    page = render_change(app, record, actor="you", profile="cloud")
    assert "tag-agent" in page              # agents carry the agent mark + tag
    assert "Policy Engine" in page
    assert "Ownership Resolver" in page
    assert "Security Operations Lead" in page   # humans carry a job title
    # An agent must never be given a human job title.
    assert "Policy Engine</span><span class=\"tag tag-agent\">" in page.replace("\n", "")


def test_scope_toggle_is_approvals_only():
    from assent.dashboard import render_app

    app = demo_app()
    threads = render_app(app, actor="you", profile="cloud", tool="chat")
    approvals = render_app(app, actor="you", profile="cloud", tool="approvals")
    assert 'action="/scope"' not in threads
    assert 'action="/scope"' in approvals
    assert ">Team<" in approvals


def test_private_profile_still_renders_shell():
    app = demo_app()
    page = render_mission(app, actor="alex", profile="private")
    assert "Assent" in page
    assert "Security Operations Lead" in page


def test_overview_lists_inventory():
    app = demo_app()
    page = render_overview(app, actor="alex", profile="cloud")
    assert "payments-api" in page or "Payments API" in page
    assert "Infrastructure" in page
    assert "pt-canvas" in page
    assert "Proposer" in page


def test_change_package_page():
    app = demo_app()
    record = app.queue()[0]
    page = render_change(app, record, actor="alex", profile="cloud")
    assert record.id in page
    assert "Executive summary" in page
    assert "Agent reasoning trace" in page
    assert "Gated remediation" in page


def test_approvals_scope_you_vs_team():
    from assent.dashboard import render_app

    app = demo_app()
    mine = render_app(app, actor="you", profile="cloud", tool="approvals", scope="you")
    team = render_app(app, actor="you", profile="cloud", tool="approvals", scope="team")
    assert "awaiting You" in mine
    assert "awaiting the team" in team
    # Team view surfaces other owners by name and job title; your own view does not.
    assert "Jordan Hale" in team and "Payments Engineering Lead" in team
    assert "Jordan Hale" not in mine


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


def test_escalate_primary_button_has_visible_label():
    app = demo_app()
    record = next(
        r for r in app.queue()
        if r.change is not None and r.decision and r.decision.value == "escalate"
    )
    page = render_change(app, record, actor="you", profile="cloud")
    assert "Take ownership" in page or "Approve" in page
    assert "Deny" in page
    # The escalate tone must not paint the primary button's label in the fill color.
    assert "btn-primary tone-escalate" in page


def test_approvals_inbox_and_audit_are_collapsible():
    from assent.dashboard import render_app

    app = demo_app()
    page = render_app(app, actor="you", profile="cloud", tool="approvals")
    assert 'data-fold="inbox"' in page
    assert 'data-fold="audit"' in page
    assert 'action="/scope"' in page
    assert ">You<" in page and ">Team<" in page
    assert "data-glass-toggle" not in page
    assert "imp-critical" not in page and "imp-high" not in page
    assert 'class="sev sev-' in page
