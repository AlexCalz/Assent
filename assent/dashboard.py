"""Assent shell — ChatGPT / Cursor desktop layout.

Left: alerts as conversation headers. Top: tools (Chat, Approvals, Infra) and a
You / other-person toggle. Main: the selected tool. Infrastructure is a Packet
Tracer-style diagram with agents pinned on the nodes they are working.
"""

from __future__ import annotations

import html
import json
from typing import Dict, List, Optional, Sequence
from urllib.parse import quote

from assent.agents import roster_for
from assent.approval_card import render_card
from assent.package import build_package
from assent.policy import PolicyResult
from assent.runtime import Assent, ChangeRecord, ChangeState
from assent.topology import render_topology

_e = html.escape

PROFILES = {
    "cloud": {
        "id": "cloud",
        "label": "Cloud · Personal / Startup",
        "tenant": "assent-cloud",
        "hint": "OAuth connectors · shared SaaS · fast start",
    },
    "private": {
        "id": "private",
        "label": "Private Tenant · Agency",
        "tenant": "agency-private",
        "hint": "SSO · audit export · air-gap ready",
    },
}

# Desk you can sit at. Toggle in the top middle switches whose inbox/audit you see.
PEOPLE: Dict[str, dict] = {
    "you": {
        "id": "you",
        "name": "You",
        "short": "You",
        "role": "SOC lead",
        "systems": frozenset(),
        "teams": frozenset({"soc"}),
        "catch_all": True,
    },
    "jordan": {
        "id": "jordan",
        "name": "Jordan Hale",
        "short": "Jordan",
        "role": "Payments owner",
        "systems": frozenset({"payments-api", "payments-latency"}),
        "teams": frozenset({"team-payments"}),
        "catch_all": False,
    },
}

_STATE_LABEL = {
    ChangeState.NEEDS_TRIAGE: "needs triage",
    ChangeState.PENDING_APPROVAL: "awaiting your approval",
    ChangeState.ESCALATED: "escalated",
    ChangeState.AUTO_EXECUTED: "auto-executed",
    ChangeState.EXECUTED: "executed after approval",
    ChangeState.DENIED: "denied",
    ChangeState.ROLLED_BACK: "rolled back",
    ChangeState.FAILED: "failed",
}
_STATE_CONTROLS = {
    ChangeState.PENDING_APPROVAL: "decide",
    ChangeState.ESCALATED: "decide",
    ChangeState.AUTO_EXECUTED: "undo",
    ChangeState.EXECUTED: "undo",
}

TOOLS = (
    ("chat", "Chat", "/"),
    ("approvals", "Approvals", "/approvals"),
    ("infra", "Infrastructure", "/infra"),
)


DASH_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --bg: #ffffff;
  --sidebar: #f7f7f4;
  --sidebar-hover: #ecece6;
  --ink: #152028;
  --ink-soft: #4a5560;
  --ink-faint: #7a858f;
  --line: rgba(21,32,40,0.10);
  --line-strong: rgba(21,32,40,0.16);
  --brand: #0f5c57;
  --brand-soft: #d7ebe8;
  --auto: #1c7a4c; --auto-bg: #e3f3ea;
  --route: #9a6410; --route-bg: #f7edd6;
  --escalate: #a93636; --escalate-bg: #f6e3e3;
  --sans: "Sora", ui-sans-serif, system-ui, sans-serif;
  --display: "Fraunces", Georgia, serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  --radius: 12px;
  --shadow: 0 1px 0 rgba(21,32,40,0.04), 0 10px 28px rgba(21,32,40,0.06);
}

* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body {
  font-family: var(--sans);
  color: var(--ink);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
button, input, select, textarea { font: inherit; }
button { cursor: pointer; }

.shell {
  height: 100vh;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
}

/* ----- sidebar (ChatGPT-style conversation list) ----- */
.sidebar {
  background: var(--sidebar);
  border-right: 1px solid var(--line);
  display: flex; flex-direction: column;
  min-height: 0;
}
.side-top {
  padding: 12px 12px 8px;
  display: flex; flex-direction: column; gap: 8px;
}
.brand-mini {
  font-family: var(--display); font-weight: 700; font-size: 22px;
  letter-spacing: -0.03em; padding: 4px 8px 2px;
}
.new-btn {
  display: flex; align-items: center; gap: 8px;
  width: 100%; border: 1px solid var(--line-strong); background: #fff;
  border-radius: 10px; padding: 9px 12px; font-weight: 600; font-size: 13px;
  color: var(--ink);
}
.new-btn:hover { border-color: var(--brand); }
.side-label {
  font-size: 11px; font-weight: 650; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink-faint); padding: 8px 16px 4px;
}
.chats {
  flex: 1; overflow: auto; padding: 4px 8px 16px;
  display: flex; flex-direction: column; gap: 2px;
}
.chat-row {
  display: grid; grid-template-columns: 8px 1fr; gap: 8px; align-items: start;
  padding: 10px 10px; border-radius: 10px; text-decoration: none;
}
.chat-row:hover { background: var(--sidebar-hover); }
.chat-row.on { background: #fff; box-shadow: 0 0 0 1px var(--line); }
.chat-row .pip {
  width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; background: #c5cdc8;
}
.chat-row.open .pip { background: var(--route); }
.chat-row.escalated .pip { background: var(--escalate); }
.chat-row.auto .pip { background: var(--auto); }
.chat-row .t {
  font-size: 13.5px; font-weight: 600; line-height: 1.3;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chat-row .p {
  font-size: 12px; color: var(--ink-faint); margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ----- main column ----- */
.maincol { display: flex; flex-direction: column; min-width: 0; min-height: 0; background: var(--bg); }

.topbar {
  height: 56px; flex: 0 0 56px;
  display: grid; grid-template-columns: 1fr auto 1fr;
  align-items: center; gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid var(--line);
}
.tools { display: flex; gap: 4px; align-items: center; }
.tool {
  text-decoration: none; font-size: 13px; font-weight: 600;
  padding: 7px 12px; border-radius: 999px; color: var(--ink-soft);
  border: 1px solid transparent;
}
.tool:hover { background: var(--sidebar); color: var(--ink); }
.tool.on { background: var(--ink); color: #f4fffc; }
.who-toggle {
  display: inline-flex; background: var(--sidebar); border: 1px solid var(--line);
  border-radius: 999px; padding: 3px;
}
.who-toggle button {
  appearance: none; border: 0; background: transparent;
  padding: 6px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 600; color: var(--ink-soft);
}
.who-toggle button.on { background: #fff; color: var(--ink); box-shadow: var(--shadow); }
.top-right {
  display: flex; justify-content: flex-end; align-items: center; gap: 8px;
}
.top-right .who { font-size: 12px; color: var(--ink-faint); }
.top-right .who strong { color: var(--ink); }
select.profile {
  border: 1px solid var(--line); border-radius: 999px;
  padding: 6px 10px; background: #fff; color: var(--ink-soft);
  font-size: 12px; max-width: 190px;
}

.workspace { flex: 1; min-height: 0; display: flex; flex-direction: column; }

/* chat thread */
.thread {
  flex: 1; overflow: auto; padding: 28px 0 12px;
}
.thread-inner { max-width: 760px; margin: 0 auto; padding: 0 24px 40px; }
.msg { display: grid; grid-template-columns: 36px 1fr; gap: 14px; margin: 0 0 22px; }
.msg.user { grid-template-columns: 1fr 36px; }
.msg.user .bubble { order: -1; background: var(--sidebar); }
.avatar {
  width: 36px; height: 36px; border-radius: 10px;
  display: grid; place-items: center;
  font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
  background: var(--brand-soft); color: var(--brand);
}
.avatar.sensor { background: #edf0f2; color: var(--ink-soft); }
.avatar.policy { background: var(--ink); color: #f4fffc; }
.avatar.audit { background: var(--route-bg); color: var(--route); }
.avatar.user { background: var(--ink); color: #fff; }
.bubble .from { font-size: 12px; font-weight: 650; margin-bottom: 4px; }
.bubble .from span { font-weight: 500; color: var(--ink-faint); margin-left: 6px; }
.bubble p { margin: 0; font-size: 14.5px; line-height: 1.55; color: var(--ink); }
.bubble ul { margin: 8px 0 0; padding-left: 18px; color: var(--ink-soft); font-size: 13.5px; }
.facts {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px;
}
.fact { background: var(--sidebar); border-radius: 10px; padding: 10px 12px; }
.fact .k { font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-faint); }
.fact .v { font-size: 13.5px; font-weight: 600; margin-top: 3px; }
.composer {
  border-top: 1px solid var(--line); padding: 12px 24px 20px;
}
.composer-box {
  max-width: 760px; margin: 0 auto;
  display: flex; gap: 8px; align-items: flex-end;
  border: 1px solid var(--line-strong); border-radius: 16px;
  padding: 8px 8px 8px 16px; background: #fff;
  box-shadow: var(--shadow);
}
.composer-box textarea {
  flex: 1; border: 0; resize: none; outline: none;
  min-height: 24px; max-height: 120px; padding: 8px 0;
  font-size: 14.5px;
}
.composer-box button {
  border: 0; background: var(--ink); color: #fff;
  border-radius: 10px; padding: 8px 14px; font-weight: 650; font-size: 13px;
}

/* approvals */
.page { flex: 1; overflow: auto; padding: 24px 28px 48px; }
.page h1 {
  font-family: var(--display); font-size: 28px; margin: 0 0 4px; letter-spacing: -0.03em;
}
.lede { margin: 0 0 22px; color: var(--ink-soft); font-size: 14px; max-width: 62ch; }
.section-h {
  display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
  margin: 8px 0 12px;
}
.section-h h2 { margin: 0; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-faint); }
.cards { display: flex; flex-direction: column; gap: 10px; }
.acard {
  border: 1px solid var(--line); border-radius: 14px; padding: 16px 16px 14px;
  background: #fff; text-decoration: none; color: inherit;
}
.acard:hover { border-color: var(--brand); }
.acard .row { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
.acard .t { font-size: 16px; font-weight: 650; }
.acard .m { font-size: 12.5px; color: var(--ink-faint); font-family: var(--mono); margin-top: 4px; }
.detail-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 12px;
}
.detail-grid .fact { background: var(--sidebar); }
.audit-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.audit-table th {
  text-align: left; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--ink-faint); font-weight: 650; padding: 8px 10px; border-bottom: 1px solid var(--line);
}
.audit-table td { padding: 12px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.audit-table .why { color: var(--ink-soft); font-size: 12.5px; max-width: 28ch; }
.audit-table code { font-family: var(--mono); font-size: 12px; }
.chain { font-size: 12.5px; margin-top: 14px; color: var(--ink-faint); }
.chain.ok { color: var(--auto); }
.chain.bad { color: var(--escalate); }

.empty {
  padding: 28px 18px; text-align: center; color: var(--ink-faint);
  border: 1px dashed var(--line-strong); border-radius: 12px; font-size: 13.5px;
}

.pill {
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  padding: 4px 8px; border-radius: 999px; white-space: nowrap;
}
.pill-auto { background: var(--auto-bg); color: var(--auto); }
.pill-route { background: var(--route-bg); color: var(--route); }
.pill-escalate { background: var(--escalate-bg); color: var(--escalate); }
.pill-triage { background: #edf0f2; color: var(--ink-faint); }

.btn {
  appearance: none; border: 1px solid var(--line-strong); border-radius: 10px;
  padding: 8px 12px; background: #fff; color: var(--ink);
  font-weight: 600; font-size: 13px; text-decoration: none;
  display: inline-flex; align-items: center; gap: 6px;
}
.btn-primary { background: var(--brand); color: #f4fffc; border-color: transparent; }
.btn-secondary { background: transparent; }

/* approval card reuse */
.remediation .card { margin: 12px 0 0; box-shadow: none; max-width: none; }
.card {
  background: #fff; border: 1px solid var(--line);
  border-radius: 14px; padding: 16px; border-left: 3px solid var(--line-strong);
}
.card.tone-auto { border-left-color: var(--auto); }
.card.tone-route { border-left-color: var(--route); }
.card.tone-escalate { border-left-color: var(--escalate); }
.card-head .action-type { margin: 8px 0 2px; font-size: 18px; letter-spacing: -0.02em; }
.card-head .stance { margin: 0; color: var(--ink-soft); font-size: 13px; }
.verdict { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge { font-size: 10.5px; font-weight: 700; padding: 3px 7px; border-radius: 999px; background: var(--sidebar); color: var(--ink-faint); }
.badge-tier0 { background: var(--escalate-bg); color: var(--escalate); }
.rec-id { font-family: var(--mono); font-size: 11px; color: var(--ink-faint); }
.command {
  margin: 12px 0; padding: 10px 12px; border-radius: 10px; background: #152028; color: #e7f2ee;
  font-family: var(--mono); font-size: 12.5px;
}
.command-label { display: block; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: #8aa39a; margin-bottom: 4px; }
.command .arrow { opacity: 0.6; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; }
.field { background: var(--sidebar); border-radius: 9px; padding: 8px 10px; }
.field-label { font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-faint); }
.field-value { font-size: 13px; font-weight: 600; margin-top: 2px; }
.field-value.mono { font-family: var(--mono); font-weight: 500; font-size: 12px; }
.tone-auto { color: var(--auto); }
.tone-route { color: var(--route); }
.tone-escalate { color: var(--escalate); }
.block { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
.block-label { font-size: 10.5px; letter-spacing: 0.07em; text-transform: uppercase; color: var(--ink-faint); font-weight: 600; margin-bottom: 4px; }
.block-body { margin: 0; font-size: 13px; color: var(--ink-soft); }
.block-body.mono { font-family: var(--mono); font-size: 12px; }
.audit-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 4px; }
.audit-conf { font-size: 12.5px; color: var(--ink-soft); }
.reasons { margin: 0; padding-left: 18px; font-size: 12.5px; color: var(--ink-soft); }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.btn-primary.tone-auto { background: var(--auto); }
.btn-primary.tone-route { background: var(--route); }
.btn-primary.tone-escalate { background: var(--escalate); }

/* packet tracer */
.pt-wrap {
  flex: 1; min-height: 0; display: flex; flex-direction: column;
  background: #eceae2; padding: 12px 16px 16px;
}
.pt-head { max-width: 1100px; margin: 0 auto 8px; width: 100%; }
.pt-head h1 { font-size: 22px; margin: 0; }
.pt-canvas {
  width: 100%; height: auto; max-height: calc(100vh - 140px);
  border: 1px solid var(--line); border-radius: 12px; background: #f3f1ea;
}
.pt-zone-label { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; fill: #7a858f; }
.pt-link { stroke: #8a959c; stroke-width: 2; }
.pt-link.hot { stroke: #0f5c57; stroke-width: 2.4; }
.pt-label { font-size: 11px; font-weight: 650; fill: #152028; font-family: var(--sans); }
.pt-meta { font-size: 9.5px; fill: #7a858f; font-family: var(--mono); }
.pt-node { cursor: pointer; }
.pt-node.on .pt-label { fill: #0f5c57; }
.agent-pin circle, .agent-pin { fill: #0f5c57; }
.agent-pin text { font-size: 9px; font-weight: 700; fill: #f4fffc; font-family: var(--sans); }
.agent-pin.pin-working circle, circle.pin-working { fill: #9a6410; }
.agent-pin.pin-blocked circle, circle.pin-blocked { fill: #a93636; }
.agent-pin.pin-complete circle, circle.pin-complete { fill: #1c7a4c; }
.pt-legend text { font-size: 11px; fill: #4a5560; font-family: var(--sans); }

.muted { color: var(--ink-faint); }
.chip { display: inline-flex; gap: 8px; padding: 6px 8px; border-radius: 8px; background: var(--sidebar); font-size: 12.5px; margin: 2px 4px 2px 0; }
.chip code { font-family: var(--mono); color: var(--brand); }

@media (max-width: 860px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .topbar { grid-template-columns: 1fr; height: auto; padding: 10px 12px; }
  .facts, .detail-grid { grid-template-columns: 1fr 1fr; }
}
"""


def _person(actor: str) -> dict:
    if actor in PEOPLE:
        return PEOPLE[actor]
    # Unknown actor (tests pass "alex") sits at the You desk under that name.
    you = dict(PEOPLE["you"])
    you["id"] = actor
    you["name"] = actor
    you["short"] = actor
    return you


def _pill_for(record: ChangeRecord) -> str:
    if record.decision is None or record.state is ChangeState.NEEDS_TRIAGE:
        return '<span class="pill pill-triage">triage</span>'
    tone = {"auto": "auto", "route_to_owner": "route", "escalate": "escalate"}.get(
        record.decision.value, "triage"
    )
    label = {"auto": "auto", "route_to_owner": "route", "escalate": "escalate"}.get(
        record.decision.value, "triage"
    )
    return f'<span class="pill pill-{tone}">{label}</span>'


def _row_class(record: ChangeRecord) -> str:
    if record.state is ChangeState.ESCALATED:
        return "escalated open"
    if record.state.open:
        return "open"
    if record.state is ChangeState.AUTO_EXECUTED:
        return "auto"
    return ""


def _alert_title(record: ChangeRecord) -> str:
    if record.change is not None:
        return f"{record.change.action.type.replace('_', ' ')} on {record.change.action.target}"
    return f"{record.signal.kind.replace('_', ' ')} on {record.signal.target}"


def _alert_preview(record: ChangeRecord) -> str:
    return record.signal.summary or f"{record.signal.source} · {record.id}"


def _inbox_for(app: Assent, person: dict) -> List[ChangeRecord]:
    """Approvals waiting on the person currently sitting at the desk."""
    waiting = app.queue()
    if person.get("catch_all"):
        others = set()
        for p in PEOPLE.values():
            if not p.get("catch_all"):
                others |= set(p.get("systems") or ())
        return [
            r for r in waiting
            if r.signal.target not in others or r.state is ChangeState.NEEDS_TRIAGE
        ]
    systems = set(person.get("systems") or ())
    teams = set(person.get("teams") or ())
    out = []
    for r in waiting:
        owner_id = r.change.owner.id if r.change is not None else ""
        if r.signal.target in systems or owner_id in teams:
            out.append(r)
    return out


def _history_for(app: Assent, person: dict) -> List[ChangeRecord]:
    """Settled changes this person (or the policy engine, for catch-all) is accountable for."""
    settled = app.settled()
    pid = person["id"]
    if person.get("catch_all") and pid in {"you", "alex"}:
        # You: human decisions by this desk, plus show policy auto-assents as context.
        return [
            r for r in settled
            if r.resolved_by in {pid, "you", "alex", "assent"}
        ]
    systems = set(person.get("systems") or ())
    return [
        r for r in settled
        if r.resolved_by == pid or r.signal.target in systems
    ]


def _sidebar(app: Assent, selected_id: Optional[str], tool: str) -> str:
    rows = []
    ordered = sorted(app.records(), key=lambda r: r.created_at, reverse=True)
    for r in ordered:
        on = " on" if r.id == selected_id else ""
        href = f"/change/{quote(r.id)}" if tool == "chat" else f"/{tool}?c={quote(r.id)}" if tool != "chat" else f"/change/{quote(r.id)}"
        if tool == "approvals":
            href = f"/approvals?c={quote(r.id)}"
        elif tool == "infra":
            href = f"/infra?c={quote(r.id)}"
        else:
            href = f"/change/{quote(r.id)}"
        rows.append(
            f"""<a class="chat-row {_row_class(r)}{on}" href="{href}">
              <span class="pip"></span>
              <div>
                <div class="t">{_e(_alert_title(r))}</div>
                <div class="p">{_e(_alert_preview(r))}</div>
              </div>
            </a>"""
        )
    body = "".join(rows) or '<div class="empty">No alerts yet.</div>'
    return f"""
    <aside class="sidebar">
      <div class="side-top">
        <div class="brand-mini">Assent</div>
        <form method="post" action="/demo">
          <button class="new-btn" type="submit">+ Simulate alert</button>
        </form>
      </div>
      <div class="side-label">Alerts</div>
      <div class="chats">{body}</div>
    </aside>
    """


def _topbar(tool: str, actor: str, profile: str) -> str:
    person = _person(actor)
    tools = []
    for key, label, href in TOOLS:
        tools.append(f'<a class="tool {"on" if tool == key else ""}" href="{href}">{label}</a>')

    selected = actor if actor in PEOPLE else "you"
    toggles = []
    for pid, p in PEOPLE.items():
        on = "on" if pid == selected else ""
        toggles.append(
            f'<button class="{on}" type="submit" name="actor" value="{pid}">{_e(p["short"])}</button>'
        )

    profile_opts = "".join(
        f'<option value="{pid}" {"selected" if pid == profile else ""} title="{_e(p["hint"])}">{_e(p["label"])}</option>'
        for pid, p in PROFILES.items()
    )
    return f"""
    <header class="topbar">
      <nav class="tools">{''.join(tools)}</nav>
      <form class="who-toggle" method="post" action="/actor">
        <input type="hidden" name="next" value="/{'' if tool == 'chat' else tool}">
        {''.join(toggles)}
      </form>
      <div class="top-right">
        <form method="post" action="/profile" style="margin:0">
          <select class="profile" name="profile" onchange="this.form.submit()" aria-label="Deployment profile">
            {profile_opts}
          </select>
        </form>
        <span class="who">acting as <strong>{_e(person['name'])}</strong> · {_e(person['role'])}</span>
      </div>
    </header>
    """


def _shell(
    *,
    app: Assent,
    tool: str,
    actor: str,
    profile: str,
    selected_id: Optional[str],
    workspace: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Assent — control plane</title>
<style>{DASH_CSS}</style>
</head>
<body>
<div class="shell">
  {_sidebar(app, selected_id, tool)}
  <div class="maincol">
    {_topbar(tool, actor, profile)}
    <div class="workspace">{workspace}</div>
  </div>
</div>
</body>
</html>
"""


def _card_for(record: ChangeRecord) -> str:
    if record.change is None:
        return f"""<div class="empty">No catalogued action — dismiss or write a playbook.
          <form method="post" action="/deny" style="margin-top:12px">
            <input type="hidden" name="id" value="{_e(record.id)}">
            <button class="btn" type="submit">Dismiss</button>
          </form></div>"""
    return render_card(
        record.change,
        PolicyResult(record.decision, record.reasons),
        record.audit,
        record_id=record.id,
        state_label=_STATE_LABEL.get(record.state, record.state.value),
        controls=_STATE_CONTROLS.get(record.state, ""),
    )


def answer_question(record: ChangeRecord, question: str) -> str:
    """Tiny retrieval over the incident package — no LLM, never a gate."""
    pkg = build_package(record)
    q = question.lower()
    if "rollback" in q or "undo" in q:
        return f"Rollback plan: {pkg.rollback}. Every write has an undo; no undo plan means no autonomy."
    if "owner" in q or "who" in q:
        return f"Authoritative owner is {pkg.owner} in {pkg.environment}. Incomplete ownership degrades to a human, never a guess."
    if "blast" in q or "radius" in q:
        return f"Blast radius: {pkg.blast_radius_narrative}. Gate key is risk-to-act (blast × reversibility × environment × confidence)."
    if "command" in q or "action" in q:
        if record.change is None:
            return "No catalogued command — this signal still needs a playbook."
        return f"Exact command: {record.change.action.type} → {record.change.action.target}."
    if "why" in q or "gate" in q or "decid" in q:
        reasons = "; ".join(pkg.gate_reasons) or "No gate reasons recorded."
        return f"The engine decided {pkg.decision} because: {reasons} Confidence never authorizes."
    if "audit" in q:
        return pkg.technical_summary
    return (
        f"{pkg.executive_summary} Ask me about owner, blast radius, rollback, "
        "the exact command, or why it was gated."
    )


def _thread_messages(
    record: ChangeRecord,
    extras: Optional[Sequence[dict]] = None,
) -> str:
    pkg = build_package(record)
    msgs = []

    def bubble(kind: str, who: str, when: str, body: str, extra: str = "") -> None:
        msgs.append(
            f"""<article class="msg">
              <div class="avatar {kind}">{_e(who[:2].upper())}</div>
              <div class="bubble">
                <div class="from">{_e(who)}<span>{_e(when)}</span></div>
                {body}{extra}
              </div>
            </article>"""
        )

    bubble(
        "sensor",
        record.signal.source,
        pkg.attack_timeline[0].timestamp if pkg.attack_timeline else "",
        f"<p>{_e(record.signal.summary)}</p>"
        + (
            "<div>" + "".join(
                f'<span class="chip"><code>{_e(k)}</code> {_e(v)}</span>'
                for k, v in record.signal.indicators.items()
            ) + "</div>"
            if record.signal.indicators
            else ""
        ),
    )
    if record.change is None:
        bubble(
            "policy",
            "Acting Proposer",
            "",
            f"<p>No playbook for <strong>{_e(record.signal.kind)}</strong>. Incomplete data degrades to ask a human — never guess and act.</p>",
        )
    else:
        bubble(
            "sensor",
            "Acting Proposer",
            "",
            f"<p>Proposed <strong>{_e(record.change.action.type)}</strong> on "
            f"<code>{_e(record.change.action.target)}</code>.</p><p>{_e(record.change.reasoning)}</p>",
        )
        owner = record.change.owner
        bubble(
            "policy",
            "Ownership Resolver",
            "",
            f"<p>Resolved owner <strong>{_e(owner.id)}</strong> from {_e(owner.source)} "
            f"(graph confidence {round(owner.confidence * 100)}% — not a gate-opener).</p>",
        )
        if record.audit is not None:
            bubble(
                "audit",
                "Independent Auditor",
                "",
                f"<p>{_e(record.audit.rationale or 'Second opinion recorded.')} "
                f"Reads {round(record.audit.confidence * 100)}% vs acting "
                f"{round(record.change.risk_envelope.confidence * 100)}%. "
                f"{'Dissent — escalate.' if record.audit.dissent else 'Can only tighten the gate.'}</p>",
            )
        reasons = "".join(f"<li>{_e(r)}</li>" for r in record.reasons) or "<li>—</li>"
        bubble(
            "policy",
            "Policy Engine",
            "",
            f"<p>Decision: {_pill_for(record)} — confidence never authorizes.</p>"
            f"<ul>{reasons}</ul>"
            f"""<div class="facts">
              <div class="fact"><div class="k">Owner</div><div class="v">{_e(pkg.owner)}</div></div>
              <div class="fact"><div class="k">Environment</div><div class="v">{_e(pkg.environment)}</div></div>
              <div class="fact"><div class="k">Blast radius</div><div class="v">{_e(pkg.blast_radius_narrative)}</div></div>
              <div class="fact"><div class="k">Reversibility</div><div class="v">{_e(pkg.reversibility)}</div></div>
              <div class="fact"><div class="k">Business impact</div><div class="v">{_e(pkg.business_impact)}</div></div>
              <div class="fact"><div class="k">Rollback</div><div class="v">{_e(pkg.rollback)}</div></div>
            </div>""",
        )
        bubble(
            "sensor",
            "Assent",
            "",
            f"<p><strong>Executive summary</strong> — {_e(pkg.executive_summary)}</p>"
            + (
                "<p class='muted' style='margin-top:8px'>MITRE (context only, not a gate input): "
                + " ".join(
                    f"<span class='chip'><code>{_e(m.id)}</code> {_e(m.name)}</span>"
                    for m in pkg.mitre_techniques
                )
                + "</p>"
                if pkg.mitre_techniques
                else ""
            ),
        )

    for extra in extras or ():
        role = extra.get("role", "user")
        if role == "user":
            msgs.append(
                f"""<article class="msg user">
                  <div class="avatar user">YO</div>
                  <div class="bubble">
                    <div class="from">You</div>
                    <p>{_e(extra.get('text', ''))}</p>
                  </div>
                </article>"""
            )
        else:
            bubble("policy", "Assent", "", f"<p>{_e(extra.get('text', ''))}</p>")

    traces = pkg.agent_trace
    trace_html = f"""
    <details class="block">
      <summary class="block-label">Agent reasoning trace</summary>
      <pre class="block-body mono" style="white-space:pre-wrap">{_e(json.dumps({
        'proposer': traces.proposer, 'ownership': traces.ownership,
        'auditor': traces.auditor, 'policy': traces.policy,
      }, indent=2))}</pre>
    </details>
    """
    card = f'<div class="remediation"><div class="block-label" style="margin-top:18px">Gated remediation</div>{_card_for(record)}{trace_html}</div>'
    return "".join(msgs) + card


def _chat_workspace(
    app: Assent,
    record: Optional[ChangeRecord],
    extras: Optional[Sequence[dict]] = None,
) -> str:
    if record is None:
        return """<div class="thread"><div class="thread-inner">
          <div class="empty">Select an alert in the sidebar — each one is a thread.</div>
        </div></div>"""
    composer = f"""
    <form class="composer" method="post" action="/ask">
      <input type="hidden" name="id" value="{_e(record.id)}">
      <div class="composer-box">
        <textarea name="q" rows="1" placeholder="Ask about owner, blast radius, rollback, or why this was gated…"></textarea>
        <button type="submit">Send</button>
      </div>
    </form>
    """
    return f"""
    <div class="thread">
      <div class="thread-inner">
        {_thread_messages(record, extras)}
      </div>
    </div>
    {composer}
    """


def _approvals_workspace(app: Assent, actor: str, selected_id: Optional[str]) -> str:
    person = _person(actor)
    inbox = _inbox_for(app, person)
    history = _history_for(app, person)
    other = PEOPLE["jordan"] if person["id"] != "jordan" else PEOPLE["you"]

    cards = []
    for r in inbox:
        on = ' style="border-color:var(--brand)"' if r.id == selected_id else ""
        ch = r.change
        cmd = f"{ch.action.type} → {ch.action.target}" if ch else "no playbook yet"
        env = ch.risk_envelope.environment.value if ch else "—"
        blast = str(ch.risk_envelope.blast_radius) if ch else "—"
        owner = ch.owner.id if ch else "unknown"
        cards.append(
            f"""<div class="acard"{on}>
              <div class="row">
                <div>
                  <div class="t"><a href="/change/{quote(r.id)}">{_e(_alert_title(r))}</a></div>
                  <div class="m">{_e(r.id)} · {_e(cmd)}</div>
                </div>
                {_pill_for(r)}
              </div>
              <div class="detail-grid">
                <div class="fact"><div class="k">Target</div><div class="v">{_e(r.signal.target)}</div></div>
                <div class="fact"><div class="k">Environment</div><div class="v">{_e(env)}</div></div>
                <div class="fact"><div class="k">Blast radius</div><div class="v">{_e(blast)}</div></div>
                <div class="fact"><div class="k">Owner</div><div class="v">{_e(owner)}</div></div>
              </div>
              {_card_for(r) if r.id == selected_id or len(inbox) == 1 else ''}
            </div>"""
        )

    inbox_html = "".join(cards) or f'<div class="empty">Nothing waiting on {_e(person["name"])}. Toggle to {_e(other["short"])} to see their inbox.</div>'

    rows = []
    for r in history:
        ch = r.change
        cmd = f"{ch.action.type}" if ch else r.signal.kind
        target = ch.action.target if ch else r.signal.target
        env = ch.risk_envelope.environment.value if ch else "—"
        blast = ch.risk_envelope.blast_radius if ch else "—"
        rev = ch.risk_envelope.reversibility.value if ch else "—"
        owner = ch.owner.id if ch else "unknown"
        why = "; ".join(r.reasons[:2]) if r.reasons else "—"
        who = r.resolved_by or "—"
        when = r.resolved_at.strftime("%H:%M:%S") if r.resolved_at else "—"
        rollback = ch.rollback if ch is not None else "—"
        rows.append(
            f"""<tr>
              <td><a href="/change/{quote(r.id)}">{_e(cmd)}</a><div class="muted">{_e(r.id)}</div></td>
              <td><code>{_e(target)}</code><div class="muted">{_e(env)} · blast { _e(str(blast)) } · {_e(rev)}</div></td>
              <td>{_pill_for(r)}<div class="muted">{_e(_STATE_LABEL.get(r.state, r.state.value))}</div></td>
              <td>{_e(who)}<div class="muted">{_e(when)}</div></td>
              <td>{_e(owner)}</td>
              <td class="why">{_e(why)}</td>
              <td>{_e(rollback)}</td>
            </tr>"""
        )
    table = "\n".join(rows) or f'<tr><td colspan="7" class="muted">No approvals recorded for {_e(person["name"])} yet. Approve something — it lands here, not in a hash table.</td></tr>'

    ok, message = app.ledger.verify()
    chain = (
        f'<div class="chain ok">Integrity: chain verified across {len(app.ledger)} entries — hashes are the receipt, not the product.</div>'
        if ok
        else f'<div class="chain bad">Integrity broken — {_e(message)}</div>'
    )

    return f"""
    <div class="page">
      <h1>Approvals</h1>
      <p class="lede">
        Desk of <strong>{_e(person["name"])}</strong> ({_e(person["role"])}).
        Toggle You / Jordan in the top middle to sit at someone else's desk —
        inbox and audit follow the person, not a shared SOC pile.
      </p>
      <div class="section-h"><h2>Inbox · waiting on {_e(person["short"])}</h2>
        <span class="muted">{len(inbox)} open</span></div>
      <div class="cards">{inbox_html}</div>

      <div class="section-h" style="margin-top:28px"><h2>Audit · {_e(person["short"])}'s decisions</h2>
        <span class="muted">command, target, envelope, who, why, rollback</span></div>
      <div style="overflow:auto; border:1px solid var(--line); border-radius:14px">
        <table class="audit-table">
          <thead><tr>
            <th>Action</th><th>Target &amp; envelope</th><th>Outcome</th>
            <th>Who / when</th><th>Owner</th><th>Why the engine gated</th><th>Rollback</th>
          </tr></thead>
          <tbody>{table}</tbody>
        </table>
      </div>
      {chain}
    </div>
    """


def _infra_workspace(app: Assent, selected_id: Optional[str]) -> str:
    agents = roster_for(app)
    selected_sys = None
    if selected_id:
        try:
            selected_sys = app.require(selected_id).signal.target
        except KeyError:
            selected_sys = None
    roster_bits = []
    for a in agents:
        roster_bits.append(
            f'<span class="chip"><strong>{_e(a.name)}</strong> · {_e(a.status.value)} — {_e(a.detail)}</span>'
        )
    return f"""
    <div class="pt-wrap">
      <div class="pt-head">
        <h1>Infrastructure</h1>
        <p class="lede">Packet Tracer view of what Assent can see. Colored zones are environments.
        Letters on a node are agents currently working that system — click a device to open its alert.</p>
        <div>{''.join(roster_bits)}</div>
      </div>
      {render_topology(app, agents, selected=selected_sys)}
    </div>
    """


def render_app(
    app: Assent,
    *,
    actor: str,
    profile: str,
    tool: str = "chat",
    selected_id: Optional[str] = None,
    extras: Optional[Sequence[dict]] = None,
) -> str:
    selected = None
    if selected_id:
        try:
            selected = app.require(selected_id)
        except KeyError:
            selected = None
    if tool == "chat" and selected is None and app.queue():
        selected = app.queue()[0]
        selected_id = selected.id

    if tool == "approvals":
        workspace = _approvals_workspace(app, actor, selected_id)
    elif tool == "infra":
        workspace = _infra_workspace(app, selected_id)
    else:
        workspace = _chat_workspace(app, selected, extras)

    return _shell(
        app=app,
        tool=tool,
        actor=actor,
        profile=profile,
        selected_id=selected_id,
        workspace=workspace,
    )


def render_mission(
    app: Assent,
    *,
    actor: str,
    profile: str,
    selected_id: Optional[str] = None,
) -> str:
    return render_app(app, actor=actor, profile=profile, tool="chat", selected_id=selected_id)


def render_change(
    app: Assent,
    record: ChangeRecord,
    *,
    actor: str,
    profile: str,
    extras: Optional[Sequence[dict]] = None,
) -> str:
    return render_app(
        app,
        actor=actor,
        profile=profile,
        tool="chat",
        selected_id=record.id,
        extras=extras,
    )


def render_overview(app: Assent, *, actor: str, profile: str) -> str:
    return render_app(app, actor=actor, profile=profile, tool="infra")


def render_ledger_page(app: Assent, *, actor: str, profile: str) -> str:
    """Kept as a route alias — the useful surface is Approvals → Audit, not a hash log."""
    return render_app(app, actor=actor, profile=profile, tool="approvals")
