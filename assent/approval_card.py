"""Approval card renderer — the hero component.

Turns a gated ``Change`` plus its deterministic ``PolicyResult`` into the human
approval surface described in ``docs/objectives.md``: exact command, target, blast
radius, reasoning, rollback, owner — and *why* the engine decided as it did. The card
is rendered from real engine output, never hand-authored, so the audit trail on screen
is exactly the one the policy engine produced.

Pure standard library. ``render_page`` emits a complete, self-contained, theme-aware
HTML document (no external assets), suitable for committing to the repo or rendering
inline.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from assent.audit import AuditOpinion
from assent.change import Change
from assent.policy import Decision, PolicyResult

# Kept in sync with AutonomyPolicy.max_audit_divergence; used only for the display label.
_AUDIT_DIVERGENCE_LABEL_THRESHOLD = 0.25


@dataclass(frozen=True)
class _Verdict:
    label: str          # the pill text
    tone: str           # css tone class: auto | route | escalate
    stance: str         # one-line framing of what the human is being asked
    primary: str        # primary button label
    secondary: str      # secondary button label


_VERDICTS = {
    Decision.AUTO: _Verdict(
        label="Auto-executed",
        tone="auto",
        stance="Low risk envelope — executed automatically, logged, and reversible.",
        primary="Undo",
        secondary="View log",
    ),
    Decision.ROUTE_TO_OWNER: _Verdict(
        label="Needs your approval",
        tone="route",
        stance="Routed to you as the authoritative owner of the affected stack.",
        primary="Approve & execute",
        secondary="Deny",
    ),
    Decision.ESCALATE: _Verdict(
        label="Escalated",
        tone="escalate",
        stance="No confident owner or a fail-safe tripped — broadened to a human decision.",
        primary="Take ownership",
        secondary="Deny",
    ),
}


def _e(text: object) -> str:
    return html.escape(str(text))


def _field(label: str, value: str, *, mono: bool = False, tone: str = "") -> str:
    cls = "field-value" + (" mono" if mono else "") + (f" tone-{tone}" if tone else "")
    return (
        '<div class="field">'
        f'<div class="field-label">{_e(label)}</div>'
        f'<div class="{cls}">{value}</div>'
        "</div>"
    )


def _audit_block(change: Change, audit: AuditOpinion) -> str:
    """Render the independent second opinion: its confidence and whether it concurs,
    diverges, or dissents from the acting agent."""
    acting = change.risk_envelope.confidence
    divergence = abs(acting - audit.confidence)
    if audit.dissent:
        stance, tone = "Dissent", "escalate"
    elif divergence > _AUDIT_DIVERGENCE_LABEL_THRESHOLD:
        stance, tone = "Diverges", "escalate"
    else:
        stance, tone = "Concurs", "auto"
    rationale = _e(audit.rationale) if audit.rationale else "no risk factors flagged"
    return f"""
        <div class="block audit">
          <div class="block-label">Independent audit · second opinion</div>
          <div class="audit-row">
            <span class="pill pill-{tone}">{stance}</span>
            <span class="audit-conf">reads <strong>{round(audit.confidence * 100)}%</strong>
              vs acting {round(acting * 100)}%</span>
          </div>
          <p class="block-body">{rationale}</p>
        </div>
    """


def render_card(
    change: Change, result: PolicyResult, audit: Optional[AuditOpinion] = None
) -> str:
    verdict = _VERDICTS[result.decision]
    action = change.action
    env = change.risk_envelope

    confidence_pct = f"{round(env.confidence * 100)}%"
    blast = f"{env.blast_radius} system" + ("" if env.blast_radius == 1 else "s")
    rev_tone = {"reversible": "auto", "recoverable": "route", "irreversible": "escalate"}[
        env.reversibility.value
    ]
    env_tone = {"dev": "auto", "staging": "route", "prod": "escalate"}[env.environment.value]

    tier0_badge = (
        '<span class="badge badge-tier0">tier-0</span>' if env.hits_tier0 else ""
    )
    owner_conf = f"{round(change.owner.confidence * 100)}%" if change.owner.known else "—"
    owner_line = (
        f'{_e(change.owner.id)} <span class="muted">· {_e(change.owner.source)} · {owner_conf}</span>'
        if change.owner.known
        else '<span class="muted">unresolved</span>'
    )

    reasons = "".join(f"<li>{_e(r)}</li>" for r in result.reasons)
    rollback = (
        _e(change.rollback)
        if change.has_rollback
        else '<span class="tone-escalate">no rollback plan — autonomy withheld</span>'
    )
    reasoning = _e(change.reasoning) if change.reasoning else '<span class="muted">—</span>'
    audit_block = _audit_block(change, audit) if audit is not None else ""

    return f"""
      <article class="card tone-{verdict.tone}">
        <header class="card-head">
          <div class="verdict">
            <span class="pill pill-{verdict.tone}">{_e(verdict.label)}</span>
            {tier0_badge}
          </div>
          <h2 class="action-type">{_e(action.type)}</h2>
          <p class="stance">{_e(verdict.stance)}</p>
        </header>

        <div class="command">
          <span class="command-label">action</span>
          <code>{_e(action.type)} <span class="arrow">→</span> {_e(action.target)}</code>
        </div>

        <div class="grid">
          {_field("Environment", _e(env.environment.value), tone=env_tone)}
          {_field("Blast radius", _e(blast))}
          {_field("Reversibility", _e(env.reversibility.value), tone=rev_tone)}
          {_field("Confidence", _e(confidence_pct))}
          {_field("Owner", owner_line)}
          {_field("Write", "yes" if action.is_write else "read-only")}
        </div>

        <div class="block">
          <div class="block-label">Reasoning</div>
          <p class="block-body">{reasoning}</p>
        </div>

        <div class="block">
          <div class="block-label">Rollback</div>
          <p class="block-body mono">{rollback}</p>
        </div>

        {audit_block}

        <div class="block trail">
          <div class="block-label">Why the engine decided this</div>
          <ul class="reasons">{reasons}</ul>
        </div>

        <footer class="actions">
          <button class="btn btn-primary tone-{verdict.tone}">{_e(verdict.primary)}</button>
          <button class="btn btn-secondary">{_e(verdict.secondary)}</button>
        </footer>
      </article>
    """


_PAGE_CSS = """
:root {
  --bg: #eef0f4;
  --surface: #ffffff;
  --surface-2: #f5f6f9;
  --border: #d6dae2;
  --border-strong: #c2c8d3;
  --ink: #1b1e26;
  --ink-soft: #565d6b;
  --ink-faint: #8990a0;
  --accent: #4f5bd5;
  --auto: #1c7a4c;   --auto-bg: #e4f4ea;   --auto-line: #b7e0c7;
  --route: #a8680a;  --route-bg: #fbeed6;  --route-line: #ecd4a3;
  --escalate: #bd3b3b; --escalate-bg: #f8e2e2; --escalate-line: #eec2c2;
  --shadow: 0 1px 2px rgba(20,24,34,.06), 0 8px 24px rgba(20,24,34,.06);
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Code", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0e1016;
    --surface: #171a22;
    --surface-2: #1e222c;
    --border: #2a2f3b;
    --border-strong: #3a4150;
    --ink: #eef0f5;
    --ink-soft: #a8b0bf;
    --ink-faint: #6c7488;
    --accent: #8b93f0;
    --auto: #57c98a;   --auto-bg: #14271d;   --auto-line: #23503a;
    --route: #e0a94e;  --route-bg: #2a2113;  --route-line: #5a4523;
    --escalate: #ea7d7d; --escalate-bg: #2a1618; --escalate-line: #5a2e30;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
  }
}
:root[data-theme="dark"] {
  --bg: #0e1016;
  --surface: #171a22;
  --surface-2: #1e222c;
  --border: #2a2f3b;
  --border-strong: #3a4150;
  --ink: #eef0f5;
  --ink-soft: #a8b0bf;
  --ink-faint: #6c7488;
  --accent: #8b93f0;
  --auto: #57c98a;   --auto-bg: #14271d;   --auto-line: #23503a;
  --route: #e0a94e;  --route-bg: #2a2113;  --route-line: #5a4523;
  --escalate: #ea7d7d; --escalate-bg: #2a1618; --escalate-line: #5a2e30;
  --shadow: 0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 760px; margin: 0 auto; padding: 48px 20px 72px; }

.masthead { margin-bottom: 28px; }
.masthead .brand {
  font-weight: 700; letter-spacing: -0.01em; font-size: 15px;
  display: inline-flex; align-items: center; gap: 8px;
}
.masthead .brand::before {
  content: ""; width: 9px; height: 9px; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent);
}
.masthead h1 { font-size: 26px; letter-spacing: -0.02em; margin: 12px 0 4px; text-wrap: balance; }
.masthead p { color: var(--ink-soft); margin: 0; font-size: 15px; max-width: 60ch; }

.queue { display: flex; flex-direction: column; gap: 20px; }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 22px 22px 18px;
  border-left: 3px solid var(--tone-line, var(--border));
}
.card.tone-auto     { --tone: var(--auto);     --tone-bg: var(--auto-bg);     --tone-line: var(--auto-line); }
.card.tone-route    { --tone: var(--route);    --tone-bg: var(--route-bg);    --tone-line: var(--route-line); }
.card.tone-escalate { --tone: var(--escalate); --tone-bg: var(--escalate-bg); --tone-line: var(--escalate-line); }

.card-head { margin-bottom: 14px; }
.verdict { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.pill {
  font-size: 12px; font-weight: 650; letter-spacing: 0.02em;
  padding: 3px 10px; border-radius: 999px;
  color: var(--tone); background: var(--tone-bg);
  border: 1px solid var(--tone-line);
}
.badge {
  font-size: 11px; font-weight: 650; letter-spacing: 0.04em; text-transform: uppercase;
  padding: 2px 7px; border-radius: 5px;
}
.badge-tier0 { color: var(--escalate); background: var(--escalate-bg); border: 1px solid var(--escalate-line); }
.action-type {
  font-family: var(--mono); font-size: 18px; font-weight: 600;
  letter-spacing: -0.01em; margin: 0; color: var(--ink);
}
.stance { margin: 4px 0 0; color: var(--ink-soft); font-size: 14px; }

.command {
  display: flex; align-items: baseline; gap: 10px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 9px; padding: 10px 12px; margin-bottom: 16px;
  overflow-x: auto;
}
.command-label {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--ink-faint); font-weight: 600; flex: none;
}
.command code { font-family: var(--mono); font-size: 13.5px; color: var(--ink); white-space: nowrap; }
.command .arrow { color: var(--ink-faint); padding: 0 2px; }

.grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: 9px; overflow: hidden;
  margin-bottom: 16px;
}
.field { background: var(--surface); padding: 10px 12px; }
.field-label {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--ink-faint); font-weight: 600; margin-bottom: 3px;
}
.field-value { font-size: 14px; color: var(--ink); font-variant-numeric: tabular-nums; }
.field-value.mono { font-family: var(--mono); font-size: 13px; }
.field-value.tone-auto { color: var(--auto); font-weight: 600; }
.field-value.tone-route { color: var(--route); font-weight: 600; }
.field-value.tone-escalate { color: var(--escalate); font-weight: 600; }
.muted { color: var(--ink-faint); font-weight: 400; }

.block { margin-bottom: 14px; }
.block-label {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--ink-faint); font-weight: 600; margin-bottom: 5px;
}
.block-body { margin: 0; font-size: 14px; color: var(--ink-soft); }
.block-body.mono { font-family: var(--mono); font-size: 13px; }

.audit {
  border: 1px solid var(--border); border-radius: 9px;
  padding: 11px 14px; margin-bottom: 14px; background: var(--surface-2);
}
.audit-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.audit-conf { font-size: 13px; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
.audit-conf strong { color: var(--ink); }

.trail {
  background: var(--tone-bg);
  border: 1px solid var(--tone-line);
  border-radius: 9px; padding: 12px 14px; margin-bottom: 18px;
}
.trail .block-label { color: color-mix(in srgb, var(--tone) 70%, var(--ink-soft)); }
.reasons { margin: 0; padding-left: 18px; }
.reasons li { font-size: 13.5px; color: var(--ink); margin: 4px 0; }
.reasons li::marker { color: var(--tone); }

.actions { display: flex; gap: 10px; }
.btn {
  font-family: var(--sans); font-size: 14px; font-weight: 600;
  padding: 9px 16px; border-radius: 8px; cursor: pointer;
  border: 1px solid transparent; transition: filter .12s ease, background .12s ease;
}
.btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.btn-primary { color: #fff; background: var(--tone, var(--accent)); }
.btn-primary:hover { filter: brightness(1.06); }
.btn-secondary { color: var(--ink-soft); background: transparent; border-color: var(--border-strong); }
.btn-secondary:hover { background: var(--surface-2); }

.foot { margin-top: 28px; color: var(--ink-faint); font-size: 12.5px; text-align: center; }
.foot code { font-family: var(--mono); }

@media (max-width: 520px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""


def render_page(
    items: Iterable[Tuple],
    *,
    title: str = "Assent — approval queue",
    intro: str = "Every action an agent proposes, gated by the deterministic policy "
    "engine. Nothing acts without assent — earned (auto) or granted (a human's).",
) -> str:
    # Each item is (change, result) or (change, result, audit).
    cards = "\n".join(
        render_card(item[0], item[1], item[2] if len(item) > 2 else None)
        for item in items
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
  <main class="wrap">
    <div class="masthead">
      <div class="brand">Assent</div>
      <h1>Approval queue</h1>
      <p>{_e(intro)}</p>
    </div>
    <div class="queue">
{cards}
    </div>
    <p class="foot">Rendered from live <code>PolicyEngine</code> output · the gate is
    computed deterministically, the card only displays it.</p>
  </main>
</body>
</html>
"""
