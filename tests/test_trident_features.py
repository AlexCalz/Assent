"""Tests for Trident-inspired Assent surfaces: agents, packages, dashboard, demo inject."""

from assent.agents import AgentStatus, roster_for
from assent.app import demo_app, inject_demo_scenario, render_ledger, render_queue
from assent.dashboard import answer_question, render_change, render_mission, render_overview
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
    assert "class=\"fabric\"" in page or 'class="fabric"' in page
    assert "class=\"topo\"" in page or 'class="topo"' in page
    assert "Production" in page
    assert "Proposer" in page or "node-live" in page


def test_change_package_page():
    app = demo_app()
    record = app.queue()[0]
    page = render_change(app, record, actor="alex", profile="cloud")
    assert record.id in page
    action = (
        record.change.action.type.replace("_", " ").capitalize()
        if record.change is not None
        else record.signal.kind.replace("_", " ").capitalize()
    )
    target = record.change.action.target if record.change is not None else record.signal.target
    assert action in page
    assert target in page
    assert f"{action} · {target}</h1>" not in page
    assert "Executive summary" in page
    assert "Agent reasoning trace" in page
    assert "Gated remediation" in page
    assert 'data-gate-toggle' in page
    assert "gate-drawer" in page
    assert 'data-fold="gate"' not in page
    assert page.find("Remediation") < page.find('class="scroll"')
    assert "Enter" in page
    assert 'aria-label="Dictate"' in page
    assert "data-dictate" in page


def test_composer_is_cursor_like_input_bar():
    app = demo_app()
    record = app.queue()[0]
    page = render_change(app, record, actor="you", profile="cloud")
    assert 'class="composer"' in page
    assert 'action="/ask"' in page
    assert 'aria-label="Dictate"' in page or "data-dictate" in page
    assert 'aria-label="Send"' in page or "composer-send" in page
    assert "composer-plus" in page or 'aria-label="Add context"' in page
    assert "composer-menu" in page
    assert "Owner &amp; blast" in page or "Owner & blast" in page
    assert "Why gated" in page
    assert "Rollback plan" in page
    assert "Incident package" in page
    assert "Policy gate" in page
    assert "composer-pill" in page
    assert 'data-equipped hidden' in page or 'data-equipped" hidden' in page
    assert "Ask about this change" in page
    assert "Assent · retrieval" in page
    assert "Enter" in page
    assert "Questions never change a gate" in page
    assert ">Ask</button>" not in page


def test_composer_tools_shape_retrieval_on_any_thread():
    app = demo_app()
    record = next(r for r in app.records() if r.change is not None)
    blast = answer_question(record, "summarize this", tools=["owner_blast"])
    assert record.change.owner.id in blast or "owner" in blast.lower()
    assert "blast" in blast.lower()
    assert "reversib" in blast.lower()
    gated = answer_question(record, "summarize this", tools=["why_gated"])
    assert "decided" in gated.lower()
    assert "confidence never authorizes" in gated.lower()
    rollback = answer_question(record, "summarize this", tools=["rollback"])
    assert "rollback" in rollback.lower()
    both = answer_question(record, "hello", tools=["owner_blast", "rollback"])
    assert "blast" in both.lower() and "rollback" in both.lower()
    general = answer_question(record, "what is going on")
    assert "Ask about the owner" in general or "executive" in general.lower() or "Gate decision" in general

    triage = next(r for r in app.records() if r.change is None)
    triage_page = render_change(app, triage, actor="you", profile="cloud")
    assert "composer-plus" in triage_page
    assert "Owner &amp; blast" in triage_page or "Owner & blast" in triage_page
    triage_why = answer_question(triage, "anything", tools=["why_gated"])
    assert "decided" in triage_why.lower()
    assert "triage" in triage_why.lower() or "playbook" in triage_why.lower()


def test_ask_http_passes_equipped_tools():
    import threading
    import time
    import urllib.parse
    import urllib.request
    from http.server import ThreadingHTTPServer

    from assent.app import _Handler

    app = demo_app()
    record = next(r for r in app.records() if r.change is not None)
    handler = type("H", (_Handler,), {"app": app, "actor": "you", "profile": "cloud", "chats": {}, "scope": "you"})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        base = f"http://127.0.0.1:{srv.server_port}"
        data = urllib.parse.urlencode([
            ("id", record.id),
            ("q", "summarize this"),
            ("tools", "owner_blast"),
        ]).encode()
        urllib.request.urlopen(base + "/ask", data=data)
        page = urllib.request.urlopen(base + f"/change/{record.id}").read().decode()
        assert "Blast radius" in page
        assert "Reversibility" in page
        assert 'id="reply"' in page
    finally:
        srv.shutdown()
        srv.server_close()


def test_thread_reply_stays_pinned_to_latest():
    app = demo_app()
    record = app.queue()[0]
    page = render_change(
        app, record, actor="you", profile="cloud",
        extras=[
            {"role": "user", "text": "why was this gated?"},
            {"role": "assistant", "text": "Because the engine escalated."},
        ],
    )
    assert 'id="reply"' in page
    assert "has-reply" in page
    assert "why was this gated?" in page
    assert 'data-gate-toggle' in page


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
    assert 'class="acard tone-' in page
    assert any(
        token in page
        for token in ("tone-escalate", "tone-route", "tone-auto", "tone-info")
    )
    assert 'class="sev sev-' in page
    assert 'class="pill pill-' in page


def test_inbox_card_tone_follows_severity_and_gate():
    from assent.dashboard import _card_tone, render_app

    app = demo_app()
    page = render_app(app, actor="you", profile="cloud", tool="approvals", scope="team")
    for record in app.queue():
        tone = _card_tone(record)
        assert tone in {"escalate", "route", "auto", "info"}
        assert f'class="acard tone-{tone}"' in page
        sev = (record.signal.severity or "medium").lower()
        decision = record.decision.value if record.decision is not None else None
        if record.state.value == "escalated" or decision == "escalate" or sev == "critical":
            assert tone == "escalate"
        elif decision == "route_to_owner" or sev == "high":
            assert tone == "route"
        elif decision == "auto" or sev == "low":
            assert tone == "auto"
        else:
            assert tone == "info"
