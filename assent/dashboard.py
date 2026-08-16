"""Dashboard shell — Assent mission control with Trident-inspired IA.

Takes the surfaces TRIDENT-AI proved useful (agent status, incident package,
remediation panel, audit trail, demo inject, three-column ops layout) and
grounds them in Assent's gating thesis:

* Approvals are ownership-routed Changes, not free-form MCP options
* Confidence is shown but never authorizes
* Dual deploy profiles (Cloud Personal / Private Tenant) share one shell

Brand: ink + stone atmosphere, Fraunces for the wordmark, Sora for UI. Not
Trident's neon-teal cyber look; not purple-on-white.
"""

from __future__ import annotations

import html
import json
from typing import List, Optional
from urllib.parse import quote

from assent.agents import AgentView, roster_for
from assent.approval_card import render_card
from assent.package import IncidentPackage, build_package
from assent.policy import PolicyResult
from assent.runtime import Assent, ChangeRecord, ChangeState

_e = html.escape

# Dual deployment profiles — same UI shell, different defaults.
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


DASH_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --bg0: #e8ebe6;
  --bg1: #f4f5f1;
  --bg: #eef0ec;
  --surface: rgba(255,255,255,0.78);
  --surface-solid: #fbfbf8;
  --surface-2: #f3f4f0;
  --ink: #152028;
  --ink-soft: #4a5560;
  --ink-faint: #7a858f;
  --line: rgba(21,32,40,0.10);
  --line-strong: rgba(21,32,40,0.18);
  --border: var(--line);
  --border-strong: var(--line-strong);
  --brand: #0f5c57;
  --brand-soft: #d7ebe8;
  --accent: #0f5c57;
  --auto: #1c7a4c; --auto-bg: #e3f3ea; --auto-line: #b7e0c7;
  --route: #9a6410; --route-bg: #f7edd6; --route-line: #ecd4a3;
  --escalate: #a93636; --escalate-bg: #f6e3e3; --escalate-line: #eec2c2;
  --shadow: 0 1px 0 rgba(21,32,40,0.04), 0 18px 40px rgba(21,32,40,0.07);
  --radius: 14px;
  --sans: "Sora", ui-sans-serif, system-ui, sans-serif;
  --display: "Fraunces", Georgia, serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}

* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; }
body {
  font-family: var(--sans);
  color: var(--ink);
  background:
    radial-gradient(1200px 600px at 10% -10%, #d9ebe7 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #ebe4d6 0%, transparent 50%),
    linear-gradient(180deg, var(--bg1), var(--bg0));
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
button, input, select { font: inherit; }

.app { min-height: 100vh; display: flex; flex-direction: column; }

/* Environment strip */
.envstrip {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 10px 22px; border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--surface-solid) 70%, transparent);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  flex-wrap: wrap;
}
.envstrip .bits { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; }
.envstrip .bit { font-size: 12px; color: var(--ink-faint); }
.envstrip .bit strong { color: var(--ink); font-weight: 600; }
.envstrip .live {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: 12px; font-weight: 600; color: var(--brand);
}
.envstrip .live::before {
  content: ""; width: 7px; height: 7px; border-radius: 50%;
  background: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 25%, transparent);
  animation: pulse 2.4s ease-in-out infinite;
}
@keyframes pulse { 50% { opacity: 0.55; } }

/* Header */
.top {
  display: flex; align-items: center; justify-content: space-between; gap: 18px;
  padding: 18px 22px 12px; flex-wrap: wrap;
}
.brand-lockup { display: flex; flex-direction: column; gap: 2px; }
.brand-lockup .word {
  font-family: var(--display); font-size: 28px; font-weight: 700;
  letter-spacing: -0.03em; line-height: 1; color: var(--ink);
}
.brand-lockup .tag {
  font-size: 12.5px; color: var(--ink-soft); max-width: 42ch;
}
.top nav { display: flex; gap: 6px; flex-wrap: wrap; }
.top nav a, .top .btn-ghost {
  text-decoration: none; font-size: 13px; font-weight: 600;
  padding: 8px 12px; border-radius: 999px; border: 1px solid transparent;
  color: var(--ink-soft); background: transparent;
}
.top nav a:hover, .top .btn-ghost:hover { background: rgba(255,255,255,0.55); color: var(--ink); }
.top nav a.on {
  background: var(--surface-solid); color: var(--ink);
  border-color: var(--line-strong); box-shadow: var(--shadow);
}
.actions-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.btn {
  appearance: none; border: 1px solid var(--line-strong); border-radius: 10px;
  padding: 9px 14px; background: var(--surface-solid); color: var(--ink);
  font-weight: 600; font-size: 13px; cursor: pointer; text-decoration: none;
  display: inline-flex; align-items: center; gap: 6px;
}
.btn:hover { border-color: var(--ink-faint); }
.btn-primary {
  background: var(--brand); color: #f4fffc; border-color: transparent;
}
.btn-primary:hover { filter: brightness(1.05); }
.btn-secondary { background: transparent; }
select.profile {
  border: 1px solid var(--line-strong); border-radius: 10px;
  padding: 8px 12px; background: var(--surface-solid); color: var(--ink);
  font-size: 12.5px; font-weight: 500;
}

/* Body grid */
.body {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 300px;
  gap: 14px; padding: 8px 18px 28px; flex: 1;
}
@media (max-width: 1100px) {
  .body { grid-template-columns: 1fr; }
  .side { order: 3; }
  .rail { order: 2; }
}
.panel {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  padding: 14px;
}
.panel h2 {
  margin: 0 0 12px; font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-faint); font-weight: 600;
}

/* Agents */
.agent {
  padding: 10px 11px; border-radius: 11px; border: 1px solid var(--line);
  background: var(--surface-solid); margin-bottom: 8px;
}
.agent:last-child { margin-bottom: 0; }
.agent .name { font-size: 13.5px; font-weight: 600; }
.agent .title { font-size: 11.5px; color: var(--ink-faint); margin-top: 1px; }
.agent .detail { font-size: 12px; color: var(--ink-soft); margin-top: 6px; }
.agent .status {
  display: inline-flex; margin-top: 8px; font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.04em; text-transform: uppercase; padding: 3px 8px; border-radius: 999px;
}
.status-idle { background: #edf0f2; color: var(--ink-faint); }
.status-working { background: var(--route-bg); color: var(--route); }
.status-complete { background: var(--auto-bg); color: var(--auto); }
.status-blocked { background: var(--escalate-bg); color: var(--escalate); }

/* Mission */
.mission { min-width: 0; }
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
@media (max-width: 720px) { .tiles { grid-template-columns: repeat(2, 1fr); } }
.tile {
  background: var(--surface-solid); border: 1px solid var(--line);
  border-radius: 12px; padding: 12px 13px;
}
.tile .n { font-size: 24px; font-weight: 700; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
.tile .l { font-size: 11.5px; color: var(--ink-faint); margin-top: 2px; }
.tile.awaiting .n { color: var(--route); }
.tile.auto .n { color: var(--auto); }

.queue-list { display: flex; flex-direction: column; gap: 8px; }
.qitem {
  display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center;
  padding: 12px 13px; border-radius: 12px; border: 1px solid var(--line);
  background: var(--surface-solid); text-decoration: none; color: inherit;
  transition: border-color .15s ease, transform .15s ease;
}
.qitem:hover { border-color: var(--brand); transform: translateY(-1px); }
.qitem.on { border-color: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 18%, transparent); }
.qitem .t { font-weight: 600; font-size: 13.5px; }
.qitem .m { font-size: 12px; color: var(--ink-faint); margin-top: 2px; font-family: var(--mono); }
.pill {
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  padding: 4px 8px; border-radius: 999px; white-space: nowrap;
}
.pill-auto { background: var(--auto-bg); color: var(--auto); }
.pill-route { background: var(--route-bg); color: var(--route); }
.pill-escalate { background: var(--escalate-bg); color: var(--escalate); }
.pill-triage { background: #edf0f2; color: var(--ink-faint); }

.empty {
  padding: 28px 18px; text-align: center; color: var(--ink-faint);
  border: 1px dashed var(--line-strong); border-radius: 12px; font-size: 13.5px;
}

/* Package */
.package { display: flex; flex-direction: column; gap: 12px; }
.pkg-head {
  display: flex; gap: 14px; align-items: flex-start; justify-content: space-between;
  flex-wrap: wrap;
}
.pkg-head h1 {
  font-family: var(--display); font-size: 26px; margin: 6px 0 4px;
  letter-spacing: -0.02em; line-height: 1.15;
}
.pkg-meta { font-size: 12.5px; color: var(--ink-faint); font-family: var(--mono); }
.gauge {
  width: 72px; height: 72px; border-radius: 50%;
  display: grid; place-items: center; position: relative;
  background: conic-gradient(var(--brand) calc(var(--p) * 1%), #dfe5e3 0);
}
.gauge::after {
  content: ""; position: absolute; inset: 7px; border-radius: 50%;
  background: var(--surface-solid);
}
.gauge span { position: relative; z-index: 1; font-weight: 700; font-size: 14px; }
.gauge small {
  position: relative; z-index: 1; display: block; font-size: 9px;
  letter-spacing: 0.06em; color: var(--ink-faint); margin-top: -2px;
}
.section {
  background: var(--surface-solid); border: 1px solid var(--line);
  border-radius: 12px; padding: 13px 14px;
}
.section .label {
  font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink-faint); font-weight: 600; margin-bottom: 8px;
}
.section p { margin: 0; font-size: 14px; color: var(--ink-soft); line-height: 1.55; }
.facts {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
@media (max-width: 720px) { .facts { grid-template-columns: 1fr; } }
.fact {
  background: var(--bg1); border-radius: 10px; padding: 10px 11px;
}
.fact .k { font-size: 10.5px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.06em; }
.fact .v { font-size: 14px; font-weight: 600; margin-top: 3px; }
.mitre, .timeline, .iocs { display: flex; flex-direction: column; gap: 6px; }
.chip {
  display: inline-flex; gap: 8px; align-items: baseline; flex-wrap: wrap;
  padding: 7px 10px; border-radius: 9px; background: var(--bg1); font-size: 12.5px;
}
.chip code { font-family: var(--mono); color: var(--brand); font-weight: 500; }
.tl { display: grid; grid-template-columns: 150px 1fr; gap: 8px; font-size: 12.5px; }
.tl .when { font-family: var(--mono); color: var(--ink-faint); }
.tl .src { color: var(--brand); font-weight: 600; font-size: 11px; }
.trace-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 720px) { .trace-grid { grid-template-columns: 1fr; } }
.trace pre {
  margin: 0; padding: 10px; border-radius: 10px; background: #152028; color: #d7e2dc;
  font-family: var(--mono); font-size: 11px; overflow: auto; max-height: 180px;
}

/* Overview map */
.map {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px;
}
.node {
  padding: 14px; border-radius: 12px; border: 1px solid var(--line);
  background: var(--surface-solid);
}
.node .sys { font-weight: 650; font-size: 14px; }
.node .meta { font-size: 12px; color: var(--ink-faint); margin-top: 4px; }
.node.prod { border-left: 3px solid var(--escalate); }
.node.staging { border-left: 3px solid var(--route); }
.node.dev { border-left: 3px solid var(--auto); }
.node.tier0 .sys::after {
  content: " tier-0"; font-size: 10px; color: var(--escalate); font-weight: 700;
}

/* Audit rail */
.audit-list { display: flex; flex-direction: column; gap: 7px; max-height: 360px; overflow: auto; }
.audit-row {
  padding: 8px 9px; border-radius: 9px; background: var(--surface-solid);
  border: 1px solid var(--line); font-size: 12px;
}
.audit-row .k { font-weight: 650; }
.audit-row .d { color: var(--ink-faint); font-family: var(--mono); font-size: 11px; margin-top: 2px; }
.chain-ok { color: var(--auto); font-weight: 650; font-size: 12.5px; }
.chain-bad { color: var(--escalate); font-weight: 650; font-size: 12.5px; }

/* Reuse approval card inside remediation panel */
.remediation .card { margin: 0; box-shadow: none; max-width: none; }
.remediation .wrap { max-width: none; padding: 0; }
.muted { color: var(--ink-faint); }
.who { font-size: 12.5px; color: var(--ink-faint); }
.who strong { color: var(--ink); }

/* Minimal approval-card primitives (from assent/approval_card.py) */
.card {
  background: var(--surface-solid); border: 1px solid var(--border);
  border-radius: 14px; padding: 16px; border-left: 3px solid var(--border-strong);
}
.card.tone-auto { border-left-color: var(--auto); }
.card.tone-route { border-left-color: var(--route); }
.card.tone-escalate { border-left-color: var(--escalate); }
.card-head .action-type { margin: 8px 0 2px; font-size: 18px; letter-spacing: -0.02em; }
.card-head .stance { margin: 0; color: var(--ink-soft); font-size: 13px; }
.verdict { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge { font-size: 10.5px; font-weight: 700; padding: 3px 7px; border-radius: 999px; background: var(--bg1); color: var(--ink-faint); }
.badge-tier0 { background: var(--escalate-bg); color: var(--escalate); }
.rec-id { font-family: var(--mono); font-size: 11px; color: var(--ink-faint); }
.command {
  margin: 12px 0; padding: 10px 12px; border-radius: 10px; background: #152028; color: #e7f2ee;
  font-family: var(--mono); font-size: 12.5px;
}
.command-label { display: block; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: #8aa39a; margin-bottom: 4px; }
.command .arrow { opacity: 0.6; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; }
.field { background: var(--bg1); border-radius: 9px; padding: 8px 10px; }
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
.btn-primary { background: var(--brand); color: #f4fffc; border-color: transparent; }
.btn-primary.tone-auto { background: var(--auto); }
.btn-primary.tone-route { background: var(--route); }
.btn-primary.tone-escalate { background: var(--escalate); }
.btn-secondary { background: transparent; }
"""


def _pill_for(record: ChangeRecord) -> str:
    if record.decision is None or record.state is ChangeState.NEEDS_TRIAGE:
        return '<span class="pill pill-triage">triage</span>'
    tone = {
        "auto": "auto",
        "route_to_owner": "route",
        "escalate": "escalate",
    }.get(record.decision.value, "triage")
    label = {
        "auto": "auto",
        "route_to_owner": "route",
        "escalate": "escalate",
    }.get(record.decision.value, "triage")
    return f'<span class="pill pill-{tone}">{label}</span>'


def _shell(
    *,
    body_main: str,
    body_side: str,
    body_rail: str,
    page: str,
    actor: str,
    profile: str,
    env_bits: str,
) -> str:
    def nav(href: str, label: str, key: str) -> str:
        return f'<a href="{href}" class="{"on" if page == key else ""}">{label}</a>'

    profile_opts = "".join(
        f'<option value="{pid}" {"selected" if pid == profile else ""}>{_e(p["label"])}</option>'
        for pid, p in PROFILES.items()
    )

    return f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Assent — control plane</title>
<style>{DASH_CSS}</style>
</head>
<body>
<div class="app">
  <div class="envstrip">
    <div class="bits">{env_bits}</div>
    <div class="live">Control plane live</div>
  </div>
  <header class="top">
    <div class="brand-lockup">
      <div class="word">Assent</div>
      <div class="tag">Nothing acts without assent — earned policy or human owner.</div>
    </div>
    <nav>
      {nav('/', 'Mission', 'mission')}
      {nav('/overview', 'Overview', 'overview')}
      {nav('/ledger', 'Ledger', 'ledger')}
    </nav>
    <div class="actions-row">
      <form method="post" action="/profile" style="margin:0">
        <select class="profile" name="profile" onchange="this.form.submit()" aria-label="Deployment profile">
          {profile_opts}
        </select>
      </form>
      <form method="post" action="/demo" style="margin:0">
        <button class="btn btn-primary" type="submit">Run demo scenario</button>
      </form>
      <span class="who">acting as <strong>{_e(actor)}</strong></span>
    </div>
  </header>
  <div class="body">
    <aside class="side">{body_side}</aside>
    <main class="mission">{body_main}</main>
    <aside class="rail">{body_rail}</aside>
  </div>
</div>
</body>
</html>
"""


def _env_bits(app: Assent, profile: str) -> str:
    p = PROFILES.get(profile, PROFILES["cloud"])
    systems = len(app.inventory.names())

    return f"""
      <div class="bit">Tenant <strong>{_e(p['tenant'])}</strong></div>
      <div class="bit">Profile <strong>{_e(p['label'])}</strong></div>
      <div class="bit">Systems in view <strong>{systems}</strong></div>
      <div class="bit">{_e(p['hint'])}</div>
    """


def _agents_panel(agents: List[AgentView]) -> str:
    cards = []
    for a in agents:
        cards.append(
            f"""<div class="agent">
              <div class="name">{_e(a.name)}</div>
              <div class="title">{_e(a.title)}</div>
              <div class="detail">{_e(a.detail)}</div>
              <span class="status status-{a.status.value}">{a.status.value}</span>
            </div>"""
        )
    return f'<div class="panel"><h2>Agent roster</h2>{"".join(cards)}</div>'


def _audit_rail(app: Assent) -> str:
    ok, message = app.ledger.verify()
    rows = []
    for entry in reversed(app.ledger.entries()[-12:]):
        rows.append(
            f"""<div class="audit-row">
              <div class="k">{_e(entry.kind)} · {_e(entry.change_id)}</div>
              <div class="d">{entry.at.strftime('%H:%M:%S')} · {_e(entry.actor)} · {_e(entry.entry_hash[:8])}…</div>
            </div>"""
        )
    chain = (
        f'<div class="chain-ok">✓ chain verified</div>'
        if ok
        else f'<div class="chain-bad">✕ chain broken — {_e(message)}</div>'
    )
    body = "".join(rows) or '<div class="empty">No ledger entries yet.</div>'
    return f"""<div class="panel"><h2>Audit trail</h2>{chain}
      <div class="audit-list" style="margin-top:10px">{body}</div>
      <div style="margin-top:10px"><a class="btn btn-secondary" href="/ledger">Open full ledger</a></div>
    </div>"""


def _remediation_panel(record: Optional[ChangeRecord]) -> str:
    if record is None:
        return """<div class="panel remediation"><h2>Remediation</h2>
          <div class="empty">Select a change to review the gated action.</div></div>"""
    if record.change is None:
        return f"""<div class="panel remediation"><h2>Remediation</h2>
          <div class="empty">No catalogued action — dismiss or write a playbook.
          <form method="post" action="/deny" style="margin-top:12px">
            <input type="hidden" name="id" value="{_e(record.id)}">
            <button class="btn" type="submit">Dismiss</button>
          </form></div></div>"""
    card = render_card(
        record.change,
        PolicyResult(record.decision, record.reasons),
        record.audit,
        record_id=record.id,
        state_label=_STATE_LABEL.get(record.state, record.state.value),
        controls=_STATE_CONTROLS.get(record.state, ""),
    )
    # Strip outer article styling conflicts by nesting
    return f'<div class="panel remediation"><h2>Gated remediation</h2>{card}</div>'


def _queue_items(records: List[ChangeRecord], selected: Optional[str]) -> str:
    if not records:
        return '<div class="empty">Queue clear — nothing waiting on a human.</div>'
    items = []
    for r in records:
        on = " on" if r.id == selected else ""
        items.append(
            f"""<a class="qitem{on}" href="/change/{quote(r.id)}">
              <div>
                <div class="t">{_e(r.title)}</div>
                <div class="m">{_e(r.id)} · {_e(r.signal.source)}</div>
              </div>
              {_pill_for(r)}
            </a>"""
        )
    return f'<div class="queue-list">{"".join(items)}</div>'


def render_mission(
    app: Assent,
    *,
    actor: str,
    profile: str,
    selected_id: Optional[str] = None,
) -> str:
    stats = app.stats()
    awaiting = len(app.queue())
    auto = stats.get("auto_executed", 0)
    executed = auto + stats.get("executed", 0)
    agents = roster_for(app)

    selected = None
    if selected_id:
        try:
            selected = app.require(selected_id)
        except KeyError:
            selected = None
    if selected is None and app.queue():
        selected = app.queue()[0]
        selected_id = selected.id

    main = f"""
    <div class="tiles">
      <div class="tile awaiting"><div class="n">{awaiting}</div><div class="l">awaiting assent</div></div>
      <div class="tile auto"><div class="n">{auto}</div><div class="l">auto-assented</div></div>
      <div class="tile"><div class="n">{executed}</div><div class="l">changes applied</div></div>
      <div class="tile"><div class="n">{stats.get('total', 0)}</div><div class="l">signals handled</div></div>
    </div>
    <div class="panel" style="margin-bottom:12px">
      <h2>Waiting on you</h2>
      {_queue_items(app.queue(), selected_id)}
    </div>
    <div class="panel">
      <h2>Recently settled</h2>
      {_queue_items(app.settled()[:6], selected_id)}
    </div>
    """
    return _shell(
        body_main=main,
        body_side=_agents_panel(agents),
        body_rail=_remediation_panel(selected) + _audit_rail(app),
        page="mission",
        actor=actor,
        profile=profile,
        env_bits=_env_bits(app, profile),
    )


def render_change(
    app: Assent,
    record: ChangeRecord,
    *,
    actor: str,
    profile: str,
) -> str:
    pkg = build_package(record)
    agents = roster_for(app)
    main = _render_package(pkg) + (
        f'<div style="margin-top:12px"><a class="btn btn-secondary" href="/">← Back to mission</a></div>'
    )
    return _shell(
        body_main=f'<div class="panel">{main}</div>',
        body_side=_agents_panel(agents),
        body_rail=_remediation_panel(record) + _audit_rail(app),
        page="mission",
        actor=actor,
        profile=profile,
        env_bits=_env_bits(app, profile),
    )


def _render_package(pkg: IncidentPackage) -> str:
    pct = round(pkg.confidence * 100)
    mitre = "".join(
        f'<div class="chip"><code>{_e(m.id)}</code> {_e(m.name)} · {_e(m.tactic)}</div>'
        for m in pkg.mitre_techniques
    ) or '<span class="muted">No MITRE mapping for this signal kind.</span>'

    timeline = "".join(
        f'<div class="tl"><div class="when">{_e(e.timestamp)}</div>'
        f'<div><span class="src">{_e(e.source)}</span> {_e(e.event)}</div></div>'
        for e in pkg.attack_timeline
    )

    ioc_bits = []
    for bucket, values in pkg.iocs.items():
        for v in values:
            ioc_bits.append(f'<div class="chip"><code>{_e(bucket)}</code> {_e(v)}</div>')
    iocs = "".join(ioc_bits) or '<span class="muted">No indicators attached.</span>'

    factors = "".join(f"<li>{_e(f)}</li>" for f in pkg.contributing_factors)
    reasons = "".join(f"<li>{_e(r)}</li>" for r in pkg.gate_reasons) or "<li>—</li>"

    traces = pkg.agent_trace
    trace_html = f"""
    <div class="trace-grid">
      <div><div class="label">Proposer</div><pre>{_e(json.dumps(traces.proposer, indent=2))}</pre></div>
      <div><div class="label">Ownership</div><pre>{_e(json.dumps(traces.ownership, indent=2))}</pre></div>
      <div><div class="label">Auditor</div><pre>{_e(json.dumps(traces.auditor, indent=2))}</pre></div>
      <div><div class="label">Policy</div><pre>{_e(json.dumps(traces.policy, indent=2))}</pre></div>
    </div>
    """

    decision_pill = {
        "auto": "pill-auto",
        "route_to_owner": "pill-route",
        "escalate": "pill-escalate",
        "triage": "pill-triage",
    }.get(pkg.decision, "pill-triage")

    return f"""
    <div class="package">
      <div class="pkg-head">
        <div>
          <span class="pill {decision_pill}">{_e(pkg.decision)}</span>
          <span class="pill pill-triage">{_e(pkg.status)}</span>
          <h1>{_e(pkg.title)}</h1>
          <div class="pkg-meta">{_e(pkg.record_id)} · threat {_e(pkg.severity)}</div>
        </div>
        <div class="gauge" style="--p:{pct}" title="Confidence never authorizes">
          <div style="text-align:center"><span>{pct}%</span><small>CONF</small></div>
        </div>
      </div>

      <div class="section">
        <div class="label">Executive summary — ready for leadership</div>
        <p>{_e(pkg.executive_summary)}</p>
      </div>

      <div class="facts">
        <div class="fact"><div class="k">Owner</div><div class="v">{_e(pkg.owner)}</div></div>
        <div class="fact"><div class="k">Environment</div><div class="v">{_e(pkg.environment)}</div></div>
        <div class="fact"><div class="k">Blast radius</div><div class="v">{_e(pkg.blast_radius_narrative)}</div></div>
        <div class="fact"><div class="k">Reversibility</div><div class="v">{_e(pkg.reversibility)}</div></div>
        <div class="fact"><div class="k">Business impact</div><div class="v">{_e(pkg.business_impact)}</div></div>
        <div class="fact"><div class="k">Rollback</div><div class="v">{_e(pkg.rollback)}</div></div>
      </div>

      <div class="section">
        <div class="label">MITRE ATT&amp;CK (contextual — not a gate input)</div>
        <div class="mitre">{mitre}</div>
      </div>

      <div class="section">
        <div class="label">Attack / decision timeline</div>
        <div class="timeline">{timeline}</div>
      </div>

      <div class="section">
        <div class="label">Indicators</div>
        <div class="iocs">{iocs}</div>
      </div>

      <div class="section">
        <div class="label">Technical root cause</div>
        <p>{_e(pkg.technical_summary)}</p>
        <ul style="margin:8px 0 0; padding-left:18px; color:var(--ink-soft); font-size:13px">{factors}</ul>
      </div>

      <div class="section">
        <div class="label">Why the engine decided this</div>
        <ul style="margin:0; padding-left:18px; color:var(--ink-soft); font-size:13px">{reasons}</ul>
      </div>

      <div class="section">
        <div class="label">Agent reasoning trace</div>
        {trace_html}
      </div>
    </div>
    """


def render_overview(app: Assent, *, actor: str, profile: str) -> str:
    """Infra overview — what the system sees (Phase 1 surface)."""
    agents = roster_for(app)
    nodes = []
    for name in app.inventory.names():
        sys = app.inventory.get(name)
        env = sys.environment.value
        tier = " tier0" if sys.tier0 else ""
        nodes.append(
            f"""<div class="node {env}{tier}">
              <div class="sys">{_e(sys.name)}</div>
              <div class="meta">{_e(env)} · blast {sys.blast_radius}</div>
            </div>"""
        )
    map_html = "".join(nodes) or '<div class="empty">No systems in inventory yet.</div>'
    main = f"""
    <div class="panel">
      <h2>Infrastructure overview</h2>
      <p class="muted" style="margin:0 0 12px; font-size:13.5px">
        What Assent can see right now. Unknown systems resolve to prod + tier-0 so they cannot auto-execute.
      </p>
      <div class="map">{map_html}</div>
    </div>
    """
    return _shell(
        body_main=main,
        body_side=_agents_panel(agents),
        body_rail=_audit_rail(app),
        page="overview",
        actor=actor,
        profile=profile,
        env_bits=_env_bits(app, profile),
    )


def render_ledger_page(app: Assent, *, actor: str, profile: str) -> str:
    ok, message = app.ledger.verify()
    rows = []
    for entry in reversed(app.ledger.entries()):
        rows.append(
            f"""<tr>
              <td class="mono">{entry.seq}</td>
              <td class="mono">{entry.at.strftime('%H:%M:%S')}</td>
              <td>{_e(entry.kind)}</td>
              <td class="mono">{_e(entry.change_id)}</td>
              <td>{_e(entry.actor)}</td>
              <td class="mono muted">{_e(entry.entry_hash[:12])}…</td>
            </tr>"""
        )
    table = "\n".join(rows) or '<tr><td colspan="6" style="text-align:center">No entries.</td></tr>'
    chain = "✓ chain verified" if ok else f"✕ chain broken — {_e(message)}"
    main = f"""
    <div class="panel">
      <h2>Tamper-evident ledger</h2>
      <p class="{'chain-ok' if ok else 'chain-bad'}">{chain}</p>
      <div style="overflow:auto; margin-top:12px">
        <table style="width:100%; border-collapse:collapse; font-size:13px">
          <thead><tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">#</th>
            <th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">Time</th>
            <th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">Event</th>
            <th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">Change</th>
            <th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">Actor</th>
            <th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">Hash</th>
          </tr></thead>
          <tbody>{table}</tbody>
        </table>
      </div>
    </div>
    """
    return _shell(
        body_main=main,
        body_side=_agents_panel(roster_for(app)),
        body_rail=_audit_rail(app),
        page="ledger",
        actor=actor,
        profile=profile,
        env_bits=_env_bits(app, profile),
    )
