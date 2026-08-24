"""Assent shell — desktop app layout.

Structure follows the conventions people already have muscle memory for
(ChatGPT / Cursor / Linear): a collapsible thread rail on the left, a tool
segment in the top bar, and one focused workspace.

Two rules the visual system exists to serve:

* An **agent** speaking is unmistakably an agent — agent mark, capability line,
  never a job title.
* A **person** speaking carries their name *and* their org job title, because
  the product's whole claim is that a named, authoritative human assented.
"""

from __future__ import annotations

import html
import json
from typing import Dict, List, Optional, Sequence
from urllib.parse import quote

from assent import identity as ident
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

# Kept for the app's actor switching; identity data itself lives in identity.py.
PEOPLE = ident.PEOPLE

_STATE_LABEL = {
    ChangeState.NEEDS_TRIAGE: "needs triage",
    ChangeState.PENDING_APPROVAL: "awaiting approval",
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
    ("chat", "Threads", "/"),
    ("approvals", "Approvals", "/approvals"),
    ("infra", "Infrastructure", "/infra"),
)

_TOOL_ICON = {
    "chat": '<svg viewBox="0 0 16 16" class="ico"><path d="M2.5 3.2h11v7.2H6.4L3.4 12.8v-2.4H2.5z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>',
    "approvals": '<svg viewBox="0 0 16 16" class="ico"><path d="M3 8.4l3 3 7-7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "infra": '<svg viewBox="0 0 16 16" class="ico"><path d="M8 2.4v3.4M4 13.6v-2.2h8v2.2M8 5.8v5.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><rect x="5.6" y="1" width="4.8" height="2.8" rx="0.8" fill="none" stroke="currentColor" stroke-width="1.3"/><rect x="2.2" y="12.6" width="3.6" height="2.6" rx="0.8" fill="none" stroke="currentColor" stroke-width="1.3"/><rect x="10.2" y="12.6" width="3.6" height="2.6" rx="0.8" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
}


DASH_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  /* neutrals — one ramp, used consistently */
  --n0: #ffffff;
  --n1: #fbfbfa;
  --n2: #f6f6f4;
  --n3: #eeeeeb;
  --n4: #e2e2de;
  --n6: #9a9a94;
  --n8: #56565230;
  --ink: #17181a;
  --ink-2: #52555a;
  --ink-3: #86898f;
  --line: #e6e6e2;
  --line-2: #d8d8d3;

  --accent: #0d5c56;
  --accent-2: #e6f1ef;
  --auto: #17714a; --auto-bg: #e8f3ec;
  --route: #8a5a0f; --route-bg: #f8efdb;
  --escalate: #a13232; --escalate-bg: #f8e6e6;

  --sans: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;
  --display: "Newsreader", Georgia, serif;
  --mono: "JetBrains Mono", ui-monospace, Menlo, monospace;

  /* type scale */
  --t-micro: 10.5px;
  --t-meta: 11.5px;
  --t-small: 12.5px;
  --t-body: 13.5px;
  --t-read: 15px;
  --t-h3: 17px;
  --t-h2: 21px;
  --t-h1: 30px;

  /* 4px spacing scale */
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 48px;

  --r-sm: 8px; --r-md: 10px; --r-lg: 14px; --r-xl: 18px;
  --rail: 292px;
  --ease: cubic-bezier(0.22, 0.75, 0.24, 1);
  --shadow-1: 0 1px 2px rgba(23,24,26,0.05);
  --shadow-2: 0 4px 16px rgba(23,24,26,0.07), 0 1px 2px rgba(23,24,26,0.05);
  --shadow-3: 0 18px 48px rgba(23,24,26,0.11), 0 2px 6px rgba(23,24,26,0.06);
}

* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body {
  font-family: var(--sans);
  font-size: var(--t-body);
  font-feature-settings: "cv11", "ss01";
  color: var(--ink);
  background: var(--n0);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
a { color: inherit; text-decoration: none; }
button, input, select, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
::selection { background: var(--accent-2); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }

/* ---------------------------------------------------------------- shell */
.shell {
  height: 100vh;
  display: grid;
  grid-template-columns: var(--rail) minmax(0, 1fr);
  transition: grid-template-columns 260ms var(--ease);
}
html[data-nav="collapsed"] .shell { grid-template-columns: 0px minmax(0, 1fr); }

.rail {
  background: var(--n2);
  border-right: 1px solid var(--line);
  display: flex; flex-direction: column;
  min-height: 0; overflow: hidden;
}
.rail-inner {
  width: var(--rail); min-width: var(--rail);
  display: flex; flex-direction: column; min-height: 0; height: 100%;
  opacity: 1; transform: translateX(0);
  transition: opacity 180ms var(--ease), transform 260ms var(--ease);
}
html[data-nav="collapsed"] .rail-inner { opacity: 0; transform: translateX(-12px); }

.rail-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--s2); padding: var(--s3) var(--s3) var(--s2) var(--s4);
}
.wordmark {
  display: flex; align-items: center;
  font-family: var(--display); font-size: var(--t-h2); letter-spacing: -0.015em;
  line-height: 1; font-weight: 500;
}
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: var(--r-sm);
  border: 1px solid transparent; background: transparent; color: var(--ink-3);
  transition: background 140ms var(--ease), color 140ms var(--ease);
}
.icon-btn:hover { background: var(--n3); color: var(--ink); }
.icon-btn svg { width: 16px; height: 16px; }

.rail-actions { padding: 0 var(--s3) var(--s3); }
.new-btn {
  display: flex; align-items: center; justify-content: center; gap: var(--s2);
  width: 100%; border: 1px solid var(--line-2); background: var(--n0);
  border-radius: var(--r-md); padding: 9px var(--s3);
  font-weight: 550; font-size: var(--t-small); color: var(--ink);
  box-shadow: var(--shadow-1);
  transition: border-color 140ms var(--ease), box-shadow 140ms var(--ease), transform 140ms var(--ease);
}
.new-btn:hover { border-color: var(--accent); box-shadow: var(--shadow-2); transform: translateY(-1px); }
.new-btn svg { width: 14px; height: 14px; }

.rail-label {
  display: flex; align-items: center; justify-content: space-between;
  font-size: var(--t-micro); font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--ink-3);
  padding: var(--s2) var(--s4) var(--s1);
}
.rail-label .count { letter-spacing: 0; font-weight: 500; }
.threads {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: var(--s1) var(--s2) var(--s5);
  display: flex; flex-direction: column; gap: 1px;
  scrollbar-width: thin;
}
.threads::-webkit-scrollbar { width: 8px; }
.threads::-webkit-scrollbar-thumb { background: var(--n4); border-radius: 8px; }

.thread-row {
  display: block;
  padding: 10px 12px; border-radius: var(--r-md);
  transition: background 140ms var(--ease);
  position: relative;
}
.thread-row:hover { background: var(--n3); }
.thread-row.on { background: var(--n0); }
.thread-row .t, .thread-row .p {
  display: block; min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.thread-row .t {
  font-size: var(--t-body); font-weight: 500; line-height: 1.35; letter-spacing: -0.005em;
}
.thread-row .p {
  font-size: var(--t-meta); color: var(--ink-3); margin-top: 2px; line-height: 1.4;
}

/* ---------------------------------------------------------------- main */
.main { display: flex; flex-direction: column; min-width: 0; min-height: 0; }

.topbar {
  height: 52px; flex: 0 0 52px;
  display: grid; grid-template-columns: 1fr auto 1fr;
  align-items: center; gap: var(--s3);
  padding: 0 var(--s4);
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--n0) 82%, transparent);
  backdrop-filter: saturate(180%) blur(12px);
  -webkit-backdrop-filter: saturate(180%) blur(12px);
}
.top-left { display: flex; align-items: center; gap: var(--s2); min-width: 0; }
.reveal { display: none; }
html[data-nav="collapsed"] .reveal { display: inline-flex; }
html[data-nav="collapsed"] .top-left .crumb-word { display: inline; }
.crumb-word {
  display: none; font-family: var(--display); font-size: var(--t-h3); letter-spacing: -0.01em;
}
.crumb {
  font-size: var(--t-small); color: var(--ink-3);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.crumb strong { color: var(--ink-2); font-weight: 550; }

.segment {
  display: inline-flex; padding: 3px; gap: 2px;
  background: var(--n2); border: 1px solid var(--line); border-radius: 999px;
}
.segment a, .segment button {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: var(--t-small); font-weight: 550; letter-spacing: -0.005em;
  padding: 6px 13px; border-radius: 999px; color: var(--ink-2);
  border: 1px solid transparent; background: transparent;
  transition: background 150ms var(--ease), color 150ms var(--ease), box-shadow 150ms var(--ease);
}
.segment a:hover, .segment button:hover { color: var(--ink); }
.segment a.on, .segment button.on {
  background: var(--n0); color: var(--ink);
  box-shadow: var(--shadow-1), 0 0 0 1px var(--line);
}
.segment .ico { width: 14px; height: 14px; }

.top-right { display: flex; align-items: center; justify-content: flex-end; gap: var(--s3); }
select.profile {
  border: 1px solid var(--line); border-radius: 999px;
  padding: 6px 10px; background: var(--n0); color: var(--ink-2);
  font-size: var(--t-meta); max-width: 178px;
  transition: border-color 140ms var(--ease);
}
select.profile:hover { border-color: var(--line-2); }

/* ---------------------------------------------------------------- identity */
.identity { display: inline-flex; align-items: center; gap: var(--s2); min-width: 0; }
.avatar {
  width: 30px; height: 30px; border-radius: 9px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: var(--t-micro); font-weight: 650; letter-spacing: 0.02em;
}
.avatar-person { background: var(--ink); color: var(--n0); }
.avatar-agent { background: var(--accent-2); color: var(--accent); border: 1px solid color-mix(in srgb, var(--accent) 22%, transparent); }
.avatar-sensor { background: var(--n3); color: var(--ink-3); }
.avatar .mark-glyph { width: 17px; height: 17px; }
.avatar.sm { width: 22px; height: 22px; border-radius: 7px; font-size: 9.5px; }
.avatar.sm .mark-glyph { width: 13px; height: 13px; }

.byline { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 1px; min-width: 0; }
.byline-row { display: inline-flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.byline-name { font-size: var(--t-body); font-weight: 600; letter-spacing: -0.008em; }
.byline-sub { font-size: var(--t-meta); color: var(--ink-3); line-height: 1.35; }
.byline-meta { font-size: var(--t-micro); color: var(--ink-3); font-family: var(--mono); }
.byline.stack { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 1px; }

.tag {
  font-size: 9.5px; font-weight: 650; letter-spacing: 0.07em; text-transform: uppercase;
  padding: 2px 6px; border-radius: 5px; line-height: 1.5;
}
.tag-agent { background: var(--accent-2); color: var(--accent); }
.tag-sensor { background: var(--n3); color: var(--ink-3); }
.tag-you { background: var(--ink); color: var(--n0); }

/* ---------------------------------------------------------------- thread */
.thread-view { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.thread-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--s4);
  padding: var(--s4) var(--s5);
  border-bottom: 1px solid var(--line);
}
.thread-head-inner { min-width: 0; flex: 1; }
.thread-head-actions { flex: none; padding-top: 2px; }
.gate-btn.on { background: var(--n2); border-color: var(--ink-3); }
.thread-head h1 {
  font-family: var(--sans); font-size: 22px; font-weight: 600;
  letter-spacing: -0.025em; line-height: 1.2; margin: var(--s2) 0 6px;
}
.thread-head .sub {
  display: flex; align-items: center; gap: var(--s3); flex-wrap: wrap;
  font-size: var(--t-small); color: var(--ink-3);
}
.thread-head .sub code { font-family: var(--mono); font-size: var(--t-meta); }

.scroll { flex: 1; overflow-y: auto; }
.scroll-inner { max-width: 780px; margin: 0 auto; padding: var(--s5) var(--s5) var(--s4); }

.msg { padding: 0 0 var(--s5); }
.thread-view.has-reply .msg { animation: none; }
@media (prefers-reduced-motion: reduce) {
  .shell, .rail-inner { transition: none; }
}

.msg-head { display: flex; align-items: center; justify-content: space-between; gap: var(--s3); }
.msg-body { padding-left: 38px; margin-top: 6px; }
.msg-body p { margin: 0 0 var(--s2); font-size: var(--t-read); line-height: 1.6; color: var(--ink); }
.msg-body p:last-child { margin-bottom: 0; }
.msg-body .quiet { color: var(--ink-2); font-size: var(--t-body); }
.msg-body ul { margin: var(--s2) 0 0; padding-left: 18px; }
.msg-body li { font-size: var(--t-body); color: var(--ink-2); line-height: 1.6; margin-bottom: 3px; }
.msg-body code { font-family: var(--mono); font-size: 12.5px; background: var(--n2); padding: 1px 5px; border-radius: 5px; }

.msg.mine .msg-body {
  padding-left: 0; margin-left: 38px;
  background: var(--n2); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: var(--s3) var(--s4);
}

.facts { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--s2); margin-top: var(--s3); }
.fact {
  background: var(--n2); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 9px 11px;
}
.fact .k {
  font-size: var(--t-micro); letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--ink-3); font-weight: 600;
}
.fact .v { font-size: var(--t-body); font-weight: 550; margin-top: 3px; line-height: 1.4; }

.thread-body {
  flex: 1; min-height: 0;
  display: grid; grid-template-columns: minmax(0, 1fr) 0px;
  transition: grid-template-columns 240ms var(--ease);
}
.thread-view.gate-open .thread-body {
  grid-template-columns: minmax(0, 1fr) minmax(300px, 400px);
}
.gate-drawer {
  min-height: 0; overflow: hidden;
  border-left: 1px solid transparent; background: var(--n1);
}
.thread-view.gate-open .gate-drawer { border-left-color: var(--line); }
.gate-drawer-inner {
  width: 400px; max-width: 100%; height: 100%;
  overflow-y: auto; padding: var(--s4);
}
.gate-drawer-inner h2 {
  margin: 0 0 var(--s3); font-size: var(--t-meta); font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);
}

.composer { border-top: 1px solid var(--line); padding: var(--s3) var(--s5) var(--s5); background: var(--n0); }
.composer-box {
  max-width: 780px; margin: 0 auto;
  display: flex; gap: var(--s2); align-items: flex-end;
  border: 1px solid var(--line-2); border-radius: var(--r-xl);
  padding: var(--s2) var(--s2) var(--s2) var(--s4); background: var(--n0);
  box-shadow: var(--shadow-2);
  transition: border-color 160ms var(--ease), box-shadow 160ms var(--ease);
}
.composer-box:focus-within { border-color: var(--accent); box-shadow: var(--shadow-3); }
.composer-box textarea {
  flex: 1; border: 0; resize: none; outline: none; background: transparent;
  min-height: 24px; max-height: 140px; padding: 7px 0; font-size: var(--t-read); line-height: 1.5;
}
.composer-box button[type="submit"] {
  border: 0; background: var(--ink); color: var(--n0);
  border-radius: var(--r-md); padding: 8px 14px; font-weight: 600; font-size: var(--t-small);
  transition: transform 140ms var(--ease), opacity 140ms var(--ease);
}
.composer-box button[type="submit"]:hover { transform: translateY(-1px); opacity: 0.92; }
.composer-box .icon-btn {
  flex: none; width: 32px; height: 32px; margin-bottom: 1px;
  color: var(--ink-3);
}
.composer-box .icon-btn:hover { color: var(--ink); background: var(--n2); }
.composer-box .icon-btn.on,
.composer-box .icon-btn[aria-pressed="true"] {
  color: var(--accent); background: var(--accent-2);
}
.composer-hint { max-width: 780px; margin: 6px auto 0; font-size: var(--t-micro); color: var(--ink-3); }

/* ---------------------------------------------------------------- pages */
.page { flex: 1; overflow-y: auto; }
.page-inner { max-width: 1180px; margin: 0 auto; padding: var(--s5) var(--s5) var(--s7); }
.page-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: var(--s4); flex-wrap: wrap; margin-bottom: var(--s5);
}
.page h1 {
  font-family: var(--display); font-size: var(--t-h1); font-weight: 400;
  letter-spacing: -0.02em; margin: 0 0 6px; line-height: 1.1;
}
.lede { margin: 0; color: var(--ink-2); font-size: var(--t-read); line-height: 1.55; max-width: 66ch; }

.stats { display: flex; gap: var(--s5); flex-wrap: wrap; margin-bottom: var(--s5); }
.stat .n {
  font-size: 26px; font-weight: 600; letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums; line-height: 1.1;
}
.stat .l { font-size: var(--t-meta); color: var(--ink-3); margin-top: 2px; }
.stat.route .n { color: var(--route); }
.stat.auto .n { color: var(--auto); }

.subhead {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--s3); margin: var(--s6) 0 var(--s3);
  padding-bottom: var(--s2); border-bottom: 1px solid var(--line);
}
.subhead:first-of-type { margin-top: 0; }
.subhead h2 {
  margin: 0; font-size: var(--t-meta); font-weight: 600;
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--ink-3);
}
.subhead .note { font-size: var(--t-meta); color: var(--ink-3); }

.cards { display: flex; flex-direction: column; gap: var(--s3); }
.acard {
  border: 1px solid var(--line); border-radius: var(--r-lg);
  background: var(--n0);
  transition: border-color 160ms var(--ease), box-shadow 160ms var(--ease);
}
.acard:hover { border-color: var(--line-2); box-shadow: var(--shadow-1); }
.acard-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--s4); padding: var(--s4);
}
.acard-title { font-size: var(--t-h3); font-weight: 600; letter-spacing: -0.012em; }
.acard-cmd { font-family: var(--mono); font-size: var(--t-meta); color: var(--ink-3); margin-top: 4px; }
.acard-meta { display: flex; gap: var(--s5); padding: 0 var(--s4) var(--s4); flex-wrap: wrap; }
.mini { min-width: 96px; }
.mini .k {
  font-size: var(--t-micro); letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--ink-3); font-weight: 600;
}
.mini .v { font-size: var(--t-body); font-weight: 550; margin-top: 2px; }
.acard-body { border-top: 1px solid var(--line); padding: var(--s4); background: var(--n1); border-radius: 0 0 var(--r-lg) var(--r-lg); }

.tbl-wrap { border: 1px solid var(--line); border-radius: var(--r-lg); overflow: hidden; background: var(--n0); }
table.tbl { width: 100%; border-collapse: collapse; }
table.tbl th {
  text-align: left; font-size: var(--t-micro); font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3);
  padding: 11px var(--s4); background: var(--n2); border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
table.tbl td { padding: var(--s3) var(--s4); border-bottom: 1px solid var(--line); vertical-align: top; font-size: var(--t-small); }
table.tbl tr:last-child td { border-bottom: 0; }
table.tbl tbody tr { transition: background 130ms var(--ease); }
table.tbl tbody tr:hover { background: var(--n1); }
table.tbl .strong { font-weight: 600; font-size: var(--t-body); white-space: nowrap; }
table.tbl td:nth-child(1) { min-width: 150px; }
table.tbl td:nth-child(4) { min-width: 190px; }
table.tbl code { font-family: var(--mono); font-size: var(--t-meta); }
table.tbl .why { color: var(--ink-2); max-width: 30ch; line-height: 1.5; }
.num { font-variant-numeric: tabular-nums; }

.footnote { margin-top: var(--s3); font-size: var(--t-meta); color: var(--ink-3); display: flex; align-items: center; gap: 6px; }
.footnote.ok { color: var(--auto); }
.footnote.bad { color: var(--escalate); }

.empty {
  padding: var(--s6) var(--s4); text-align: center; color: var(--ink-3);
  border: 1px dashed var(--line-2); border-radius: var(--r-lg); font-size: var(--t-body);
  background: var(--n1);
}

.pill {
  font-size: 9.5px; font-weight: 650; letter-spacing: 0.07em; text-transform: uppercase;
  padding: 3px 8px; border-radius: 6px; white-space: nowrap; line-height: 1.6;
}
.pill-auto { background: var(--auto-bg); color: var(--auto); }
.pill-route { background: var(--route-bg); color: var(--route); }
.pill-escalate { background: var(--escalate-bg); color: var(--escalate); }
.pill-triage { background: var(--n3); color: var(--ink-3); }
.signals { display: inline-flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sev {
  display: inline-flex; align-items: center;
  font-size: 11px; font-weight: 650; letter-spacing: 0.04em;
  text-transform: uppercase; font-variant-numeric: tabular-nums;
}
.sev::before {
  content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  margin-right: 6px; vertical-align: 0.5px; background: currentColor;
}
.sev-critical { color: var(--escalate); }
.sev-high { color: var(--route); }
.sev-medium { color: var(--ink-2); }
.sev-low { color: var(--auto); }

.btn {
  appearance: none; border: 1px solid var(--line-2); border-radius: var(--r-md);
  padding: 8px 13px; background: var(--n0); color: var(--ink);
  font-weight: 550; font-size: var(--t-small);
  display: inline-flex; align-items: center; gap: 6px;
  transition: border-color 140ms var(--ease), transform 140ms var(--ease), box-shadow 140ms var(--ease);
}
.btn:hover { border-color: var(--ink-3); transform: translateY(-1px); box-shadow: var(--shadow-1); }
.btn-primary { background: var(--accent); color: #ffffff; border-color: transparent; }
.btn-primary:hover { border-color: transparent; }
.btn-secondary { background: transparent; }
.actions .btn { min-height: 38px; padding: 8px 16px; white-space: nowrap; color: inherit; }
.actions .btn-primary { color: #ffffff; }

/* approval card primitives */
.card { background: var(--n0); border: 1px solid var(--line); border-radius: var(--r-lg); padding: var(--s4); border-left: 3px solid var(--line-2); }
.card.tone-auto { border-left-color: var(--auto); }
.card.tone-route { border-left-color: var(--route); }
.card.tone-escalate { border-left-color: var(--escalate); }
.card-head .action-type { margin: var(--s2) 0 2px; font-size: var(--t-h3); letter-spacing: -0.015em; }
.card-head .stance { margin: 0; color: var(--ink-2); font-size: var(--t-small); line-height: 1.5; }
.verdict { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge { font-size: 9.5px; font-weight: 650; padding: 3px 7px; border-radius: 6px; background: var(--n2); color: var(--ink-3); letter-spacing: 0.06em; text-transform: uppercase; }
.badge-tier0 { background: var(--escalate-bg); color: var(--escalate); }
.rec-id { font-family: var(--mono); font-size: var(--t-micro); color: var(--ink-3); }
.command {
  margin: var(--s3) 0; padding: 11px var(--s3); border-radius: var(--r-md);
  background: #16181b; color: #e8f1ee; font-family: var(--mono); font-size: var(--t-small);
  overflow-x: auto;
}
.command-label { display: block; font-size: 9.5px; letter-spacing: 0.09em; text-transform: uppercase; color: #8ba49b; margin-bottom: 5px; }
.command .arrow { opacity: 0.55; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s2); margin: var(--s3) 0; }
.field { background: var(--n2); border-radius: var(--r-sm); padding: 8px 10px; }
.field-label { font-size: var(--t-micro); letter-spacing: 0.07em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; }
.field-value { font-size: var(--t-body); font-weight: 550; margin-top: 2px; }
.field-value.mono { font-family: var(--mono); font-weight: 400; font-size: var(--t-small); }
.field-value.tone-auto, span.tone-auto { color: var(--auto); }
.field-value.tone-route, span.tone-route { color: var(--route); }
.field-value.tone-escalate, span.tone-escalate { color: var(--escalate); }
.block { margin-top: var(--s3); padding-top: var(--s3); border-top: 1px solid var(--line); }
.block-label { font-size: var(--t-micro); letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; margin-bottom: 5px; }
.block-body { margin: 0; font-size: var(--t-small); color: var(--ink-2); line-height: 1.55; }
.block-body.mono { font-family: var(--mono); font-size: var(--t-meta); }
.audit-row { display: flex; gap: var(--s2); align-items: center; flex-wrap: wrap; margin-bottom: 4px; }
.audit-conf { font-size: var(--t-small); color: var(--ink-2); }
.reasons { margin: 0; padding-left: 17px; font-size: var(--t-small); color: var(--ink-2); line-height: 1.6; }
.actions { display: flex; gap: var(--s2); flex-wrap: wrap; margin-top: var(--s4); }
.btn-primary.tone-auto { background: var(--auto); color: #ffffff; }
.btn-primary.tone-route { background: var(--route); color: #ffffff; }
.btn-primary.tone-escalate { background: var(--escalate); color: #ffffff; }

details.trace { margin-top: var(--s3); }
details.trace summary {
  cursor: pointer; font-size: var(--t-micro); letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-3); font-weight: 600;
  list-style: none; display: flex; align-items: center; gap: 6px;
}
details.trace summary::-webkit-details-marker { display: none; }
details.trace summary::before {
  content: "▸"; font-size: 10px; transition: transform 160ms var(--ease);
}
details.trace[open] summary::before { transform: rotate(90deg); }
details.trace pre {
  margin: var(--s2) 0 0; padding: var(--s3); border-radius: var(--r-md);
  background: var(--n2); border: 1px solid var(--line);
  font-family: var(--mono); font-size: var(--t-meta); line-height: 1.55;
  max-height: 260px; overflow: auto; color: var(--ink-2);
}

/* ---------------------------------------------------------------- infra */
.infra { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow-y: auto; }
.infra-inner { max-width: 1480px; width: 100%; margin: 0 auto; padding: var(--s5) var(--s5) var(--s6); }
.roster {
  display: flex; flex-wrap: wrap;
  border: 1px solid var(--line); border-radius: var(--r-lg);
  overflow: hidden; background: var(--n0); margin: 0 0 var(--s5);
}
.roster-item {
  display: flex; align-items: flex-start; gap: 12px;
  flex: 1 1 240px; min-width: 240px;
  border-right: 1px solid var(--line); border-bottom: 1px solid var(--line);
  padding: 16px 18px; background: var(--n0);
}
.roster-item .byline { flex: 1; min-width: 0; }
.roster-item .status-dot { width: 7px; height: 7px; border-radius: 50%; margin-left: auto; margin-top: 6px; flex: none; }
.dot-working { background: var(--route); }
.dot-blocked { background: var(--escalate); }
.dot-complete { background: var(--auto); }
.dot-idle { background: var(--n4); }
.roster-item .detail {
  font-size: var(--t-meta); color: var(--ink-3); margin-top: 3px;
  line-height: 1.4; white-space: normal; overflow: visible; text-overflow: unset;
}

.fabric {
  border: 1px solid var(--line); border-radius: var(--r-lg);
  overflow: hidden; background: var(--n1);
}
.topo { width: 100%; height: auto; display: block; background: var(--n1); }
.topo-zone rect { fill: #fcfcfb; stroke: var(--line); stroke-width: 1; }
.topo-zone text {
  font-size: 11px; font-weight: 650; letter-spacing: 0.12em;
  text-transform: uppercase; fill: #86898f; font-family: var(--sans);
}
.topo-link { fill: none; stroke: #d4d4ce; stroke-width: 1.35; }
.topo-link.hot { stroke: color-mix(in srgb, var(--accent) 32%, #c8c8c2); stroke-width: 1.55; }
.node { cursor: pointer; }
.node.muted { cursor: default; }
.node-plate { fill: #ffffff; stroke: var(--line-2); stroke-width: 1; }
.node:hover .node-plate { stroke: #b8b8b2; }
.node.on .node-plate { stroke: var(--ink); stroke-width: 1.35; }
.node-name {
  font-size: 13.5px; font-weight: 600; fill: #17181a;
  font-family: var(--sans); letter-spacing: -0.01em;
}
.node-meta { font-size: 11px; fill: #86898f; font-family: var(--sans); }
.topo-legend text { font-size: 12px; fill: #86898f; font-family: var(--sans); }

.muted { color: var(--ink-3); }
.chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px;
  border-radius: 6px; background: var(--n2); border: 1px solid var(--line);
  font-size: var(--t-meta); margin: 2px 4px 2px 0; color: var(--ink-2);
}
.chip code { font-family: var(--mono); color: var(--accent); font-size: var(--t-micro); }

/* ---------------------------------------------------------------- folds */
.fold { margin: 0 0 var(--s5); }
.fold > summary {
  list-style: none; cursor: pointer;
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--s3); margin: 0 0 var(--s3);
  padding-bottom: var(--s2); border-bottom: 1px solid var(--line);
  user-select: none;
}
.fold > summary::-webkit-details-marker { display: none; }
.fold > summary h2 {
  margin: 0; font-size: var(--t-meta); font-weight: 600;
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--ink-3);
  display: inline-flex; align-items: center; gap: 8px;
}
.fold > summary h2::before {
  content: ""; width: 6px; height: 6px; border-right: 1.6px solid var(--ink-3);
  border-bottom: 1.6px solid var(--ink-3); transform: rotate(-45deg);
  transition: transform 220ms var(--ease);
}
.fold[open] > summary h2::before { transform: rotate(45deg); }
.fold > summary .note { font-size: var(--t-meta); color: var(--ink-3); }
.fold-body { overflow: hidden; }

@media (max-width: 900px) {
  .shell { grid-template-columns: 0 1fr; }
  .rail { display: none; }
  .topbar { grid-template-columns: auto 1fr auto; }
  .facts { grid-template-columns: 1fr 1fr; }
}
"""

_NAV_SCRIPT = """
(function () {
  var root = document.documentElement;
  try {
    if (localStorage.getItem('assent-nav') === 'collapsed') root.dataset.nav = 'collapsed';
  } catch (e) {}
  window.assentToggleNav = function () {
    var next = root.dataset.nav === 'collapsed' ? 'open' : 'collapsed';
    root.dataset.nav = next;
    try { localStorage.setItem('assent-nav', next); } catch (e) {}
  };

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    document.querySelectorAll('details.fold[data-fold]').forEach(function (el) {
      var key = 'assent-fold-' + el.dataset.fold;
      try {
        var saved = localStorage.getItem(key);
        if (saved === 'closed') el.open = false;
        if (saved === 'open') el.open = true;
      } catch (e) {}
      el.addEventListener('toggle', function () {
        try { localStorage.setItem(key, el.open ? 'open' : 'closed'); } catch (e) {}
      });
    });

    document.querySelectorAll('textarea[name="q"]').forEach(function (ta) {
      var grow = function () {
        ta.style.height = 'auto';
        ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
      };
      ta.addEventListener('input', grow);
      ta.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          var form = ta.closest('form');
          if (!form) return;
          if (typeof form.requestSubmit === 'function') form.requestSubmit();
          else form.submit();
        }
      });
      grow();

      var mic = ta.closest('form') && ta.closest('form').querySelector('[data-dictate]');
      if (mic) bindDictate(ta, mic, grow);
    });

    function bindDictate(ta, btn, grow) {
      var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        btn.title = 'Speech recognition is not available in this browser';
        btn.addEventListener('click', function (e) { e.preventDefault(); });
        return;
      }
      var rec = null;
      var listening = false;
      var base = '';
      var setOn = function (on) {
        listening = on;
        btn.classList.toggle('on', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      };
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        if (listening) {
          if (rec) try { rec.stop(); } catch (err) {}
          return;
        }
        rec = new SR();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = document.documentElement.lang || 'en-US';
        base = ta.value;
        rec.onresult = function (ev) {
          var interim = '';
          var finals = '';
          for (var i = ev.resultIndex; i < ev.results.length; i++) {
            var t = ev.results[i][0].transcript;
            if (ev.results[i].isFinal) finals += t;
            else interim += t;
          }
          if (finals) {
            base = (base && !/\\s$/.test(base) ? base + ' ' : base) + finals.replace(/^\\s+/, '');
          }
          var next = base;
          if (interim) next = (next && !/\\s$/.test(next) ? next + ' ' : next) + interim.replace(/^\\s+/, '');
          ta.value = next;
          grow();
        };
        rec.onend = function () { setOn(false); rec = null; };
        rec.onerror = function () { setOn(false); };
        try { rec.start(); setOn(true); } catch (err) { setOn(false); }
      });
    }

    try { if ('scrollRestoration' in history) history.scrollRestoration = 'manual'; } catch (e) {}
    var sc = document.querySelector('.scroll');
    if (sc && location.hash === '#reply') {
      sc.scrollTop = sc.scrollHeight;
      var reply = document.getElementById('reply');
      if (reply) reply.scrollIntoView({ block: 'nearest' });
    }

    var tv = document.querySelector('.thread-view');
    var gateBtn = document.querySelector('[data-gate-toggle]');
    if (tv && gateBtn) {
      var setGate = function (open) {
        tv.classList.toggle('gate-open', open);
        gateBtn.classList.toggle('on', open);
        gateBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        try { localStorage.setItem('assent-gate', open ? 'open' : 'closed'); } catch (e) {}
      };
      var start = location.hash === '#gate';
      try {
        if (!start && localStorage.getItem('assent-gate') === 'open') start = true;
      } catch (e) {}
      setGate(start);
      gateBtn.addEventListener('click', function () {
        setGate(!tv.classList.contains('gate-open'));
      });
    }
  });
})();
"""

_ICON_PANEL = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.8" y="2.8" width="12.4" height="10.4" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6.2 2.8v10.4" stroke="currentColor" stroke-width="1.3"/></svg>'
_ICON_PLUS = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3.4v9.2M3.4 8h9.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'
_ICON_MIC = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="6" y="1.6" width="4" height="7.2" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M3.8 7.4a4.2 4.2 0 0 0 8.4 0M8 11.6v2.2M5.6 13.8h4.8" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>'


# --------------------------------------------------------------------- helpers


def _pill_for(record: ChangeRecord) -> str:
    if record.decision is None or record.state is ChangeState.NEEDS_TRIAGE:
        return '<span class="pill pill-triage">triage</span>'
    key = {"auto": "auto", "route_to_owner": "route", "escalate": "escalate"}.get(
        record.decision.value, "triage"
    )
    label = {"auto": "auto", "route": "needs owner", "escalate": "escalated"}[key] if key != "auto" else "auto"
    return f'<span class="pill pill-{key}">{label}</span>'


def _sev_chip(record: ChangeRecord) -> str:
    severity = (record.signal.severity or "medium").lower()
    if severity not in {"critical", "high", "medium", "low"}:
        severity = "medium"
    label = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}[severity]
    return f'<span class="sev sev-{severity}">{label}</span>'


def _titlecase_action(raw: str) -> str:
    return raw.replace("_", " ").strip().capitalize()


def _alert_title(record: ChangeRecord) -> str:
    if record.change is not None:
        return f"{_titlecase_action(record.change.action.type)} · {record.change.action.target}"
    return f"{_titlecase_action(record.signal.kind)} · {record.signal.target}"


def _alert_preview(record: ChangeRecord) -> str:
    return record.signal.summary or f"{record.signal.source} · {record.id}"


def _assignee_for(record: ChangeRecord):
    """Which human this change is routed to.

    An escalation is by definition *broadened* past the stack owner, so it lands
    on the security lead rather than the team that happens to own the target.
    """
    if record.change is None or record.state is ChangeState.ESCALATED:
        return ident.person("you")
    owner_id = record.change.owner.id
    for pid, team in ident.TEAM_OF.items():
        if team == owner_id:
            return ident.person(pid)
    for pid, systems in ident.SYSTEMS_OF.items():
        if record.signal.target in systems:
            return ident.person(pid)
    return ident.person("you")


def _inbox_for(app: Assent, actor: str, scope: str) -> List[ChangeRecord]:
    waiting = app.queue()
    if scope == "team":
        return waiting
    me = ident.person(actor)
    return [r for r in waiting if _assignee_for(r).id == me.id]


def _history_for(app: Assent, actor: str, scope: str) -> List[ChangeRecord]:
    settled = app.settled()
    if scope == "team":
        return settled
    me = ident.person(actor)
    return [
        r for r in settled
        if r.resolved_by == me.id
        or (me.id in {"you", "alex"} and r.resolved_by in {"assent", "you", "alex"})
    ]


# --------------------------------------------------------------------- chrome


def _rail(app: Assent, selected_id: Optional[str], tool: str) -> str:
    rows = []
    ordered = sorted(app.records(), key=lambda r: r.created_at, reverse=True)
    open_count = len(app.queue())
    for r in ordered:
        on = " on" if r.id == selected_id else ""
        if tool == "approvals":
            href = f"/approvals?c={quote(r.id)}"
        elif tool == "infra":
            href = f"/infra?c={quote(r.id)}"
        else:
            href = f"/change/{quote(r.id)}"
        rows.append(
            f"""<a class="thread-row{on}" href="{href}">
              <span class="t">{_e(_alert_title(r))}</span>
              <span class="p">{_e(_alert_preview(r))}</span>
            </a>"""
        )
    body = "".join(rows) or '<div class="empty">No alerts yet.</div>'
    return f"""
    <aside class="rail">
      <div class="rail-inner">
        <div class="rail-head">
          <span class="wordmark">Assent</span>
          <button class="icon-btn" type="button" onclick="assentToggleNav()"
                  title="Hide alerts" aria-label="Hide alerts">{_ICON_PANEL}</button>
        </div>
        <div class="rail-actions">
          <form method="post" action="/demo">
            <button class="new-btn" type="submit">{_ICON_PLUS} Simulate alert</button>
          </form>
        </div>
        <div class="rail-label"><span>Alerts</span><span class="count">{open_count} open</span></div>
        <nav class="threads">{body}</nav>
      </div>
    </aside>
    """


def _topbar(app: Assent, tool: str, actor: str, profile: str, crumb: str) -> str:
    me = ident.person(actor)
    tools = "".join(
        f'<a class="{"on" if tool == key else ""}" href="{href}">{_TOOL_ICON[key]}{label}</a>'
        for key, label, href in TOOLS
    )
    return f"""
    <header class="topbar">
      <div class="top-left">
        <button class="icon-btn reveal" type="button" onclick="assentToggleNav()"
                title="Show alerts" aria-label="Show alerts">{_ICON_PANEL}</button>
        <span class="crumb-word">Assent</span>
        <span class="crumb">{crumb}</span>
      </div>
      <nav class="segment">{tools}</nav>
      <div class="top-right">
        <span class="identity" title="You are acting as {_e(me.name)}">
          {ident.avatar(me, size="sm")}
          <span class="byline stack">
            <span class="byline-row"><span class="byline-name">{_e(me.name)}</span></span>
            <span class="byline-sub">{_e(me.subtitle)}</span>
          </span>
        </span>
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
    crumb: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Assent — control plane</title>
<style>{DASH_CSS}</style>
<script>{_NAV_SCRIPT}</script>
</head>
<body>
<div class="shell">
  {_rail(app, selected_id, tool)}
  <div class="main">
    {_topbar(app, tool, actor, profile, crumb)}
    {workspace}
  </div>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------- thread


def _card_for(record: ChangeRecord) -> str:
    if record.change is None:
        return f"""<div class="empty">No catalogued action for this signal — it needs a
          playbook before an agent may propose anything.
          <form method="post" action="/deny" style="margin-top:16px">
            <input type="hidden" name="id" value="{_e(record.id)}">
            <button class="btn" type="submit">Dismiss signal</button>
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
        return f"Blast radius: {pkg.blast_radius_narrative}. The gate keys on risk-to-act — blast radius × reversibility × environment × confidence."
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
        f"{pkg.executive_summary} Ask about the owner, blast radius, rollback, "
        "the exact command, or why it was gated."
    )


def _message(participant, body: str, *, meta: str = "", mine: bool = False, msgid: str = "") -> str:
    cls = "msg mine" if mine else "msg"
    ident_attr = f' id="{_e(msgid)}"' if msgid else ""
    return f"""
    <article class="{cls}"{ident_attr}>
      <div class="msg-head">{ident.identity(participant, meta=meta, is_self=mine)}</div>
      <div class="msg-body">{body}</div>
    </article>"""


def _thread_messages(record: ChangeRecord, extras: Optional[Sequence[dict]] = None) -> str:
    pkg = build_package(record)
    msgs: List[str] = []

    indicators = "".join(
        f'<span class="chip"><code>{_e(k)}</code> {_e(v)}</span>'
        for k, v in record.signal.indicators.items()
    )
    msgs.append(_message(
        ident.sensor(record.signal.source),
        f"<p>{_e(record.signal.summary)}</p>" + (f"<div>{indicators}</div>" if indicators else ""),
        meta=pkg.attack_timeline[0].timestamp if pkg.attack_timeline else "",
    ))

    if record.change is None:
        msgs.append(_message(
            ident.AGENTS["proposer"],
            f"<p>No playbook covers <code>{_e(record.signal.kind)}</code>, so I am not "
            f"proposing an action. Incomplete data degrades to asking a human — never guess and act.</p>",
        ))
    else:
        change = record.change
        msgs.append(_message(
            ident.AGENTS["proposer"],
            f"<p>Proposing <code>{_e(change.action.type)}</code> on "
            f"<code>{_e(change.action.target)}</code>.</p>"
            f"<p class=\"quiet\">{_e(change.reasoning)}</p>",
        ))
        owner = change.owner
        msgs.append(_message(
            ident.AGENTS["ownership"],
            f"<p>Authoritative owner is <strong>{_e(owner.id)}</strong>, resolved from "
            f"{_e(owner.source)} with {round(owner.confidence * 100)}% graph confidence. "
            f"Graph confidence can route, never authorize.</p>",
        ))
        if record.audit is not None:
            verdict = "Dissenting — this escalates." if record.audit.dissent else "Concurring; I can only tighten the gate."
            msgs.append(_message(
                ident.AGENTS["auditor"],
                f"<p>{_e(record.audit.rationale or 'No additional risk factors flagged.')}</p>"
                f"<p class=\"quiet\">I read {round(record.audit.confidence * 100)}% against the "
                f"proposer's {round(change.risk_envelope.confidence * 100)}%. {verdict}</p>",
            ))
        reasons = "".join(f"<li>{_e(r)}</li>" for r in record.reasons) or "<li>—</li>"
        msgs.append(_message(
            ident.AGENTS["policy"],
            f"<p>Decision: {_pill_for(record)}</p><ul>{reasons}</ul>"
            f"""<div class="facts">
              <div class="fact"><div class="k">Owner</div><div class="v">{_e(pkg.owner)}</div></div>
              <div class="fact"><div class="k">Environment</div><div class="v">{_e(pkg.environment)}</div></div>
              <div class="fact"><div class="k">Blast radius</div><div class="v">{_e(pkg.blast_radius_narrative)}</div></div>
              <div class="fact"><div class="k">Reversibility</div><div class="v">{_e(pkg.reversibility)}</div></div>
              <div class="fact"><div class="k">Business impact</div><div class="v">{_e(pkg.business_impact)}</div></div>
              <div class="fact"><div class="k">Rollback</div><div class="v">{_e(pkg.rollback)}</div></div>
            </div>""",
        ))
        mitre = "".join(
            f'<span class="chip"><code>{_e(m.id)}</code> {_e(m.name)}</span>'
            for m in pkg.mitre_techniques
        )
        msgs.append(_message(
            ident.AGENTS["assent"],
            f"<p><strong>Executive summary.</strong> {_e(pkg.executive_summary)}</p>"
            + (f'<p class="quiet">MITRE context — enrichment only, never a gate input:</p><div>{mitre}</div>' if mitre else ""),
        ))

    extras_list = list(extras or ())
    for i, extra in enumerate(extras_list):
        last = i == len(extras_list) - 1
        if extra.get("role") == "user":
            msgs.append(_message(
                ident.person("you"),
                f"<p>{_e(extra.get('text', ''))}</p>",
                mine=True,
                msgid="reply" if last else "",
            ))
        else:
            msgs.append(_message(
                ident.AGENTS["assent"],
                f"<p>{_e(extra.get('text', ''))}</p>",
                msgid="reply" if last else "",
            ))

    return "".join(msgs)


def _gate_panel(record: ChangeRecord) -> str:
    pkg = build_package(record)
    traces = pkg.agent_trace
    trace_json = json.dumps(
        {
            "proposer": traces.proposer,
            "ownership": traces.ownership,
            "auditor": traces.auditor,
            "policy": traces.policy,
        },
        indent=2,
    )
    return f"""
    <aside class="gate-drawer" id="gate-panel">
      <div class="gate-drawer-inner">
        <h2>Gated remediation</h2>
        {_card_for(record)}
        <details class="trace"><summary>Agent reasoning trace</summary><pre>{_e(trace_json)}</pre></details>
      </div>
    </aside>"""


def _thread_workspace(record: Optional[ChangeRecord], extras: Optional[Sequence[dict]] = None) -> str:
    if record is None:
        return """<div class="page"><div class="page-inner">
          <div class="empty">Select an alert on the left. Each one is a thread —
          sensor, agents, and the gate decision in order.</div>
        </div></div>"""
    assignee = _assignee_for(record)
    extras = extras or ()
    replied = " has-reply" if extras else ""
    return f"""
    <div class="thread-view{replied}">
      <div class="thread-head">
        <div class="thread-head-inner">
          <div class="signals">{_sev_chip(record)}{_pill_for(record)}</div>
          <h1>{_e(_alert_title(record))}</h1>
          <div class="sub">
            <code>{_e(record.id)}</code>
            <span>routed to {_e(assignee.name)} · {_e(assignee.subtitle)}</span>
          </div>
        </div>
        <div class="thread-head-actions">
          <button class="btn gate-btn" type="button" data-gate-toggle aria-expanded="false" aria-controls="gate-panel">
            Remediation
          </button>
        </div>
      </div>
      <div class="thread-body">
        <div class="scroll"><div class="scroll-inner">{_thread_messages(record, extras)}</div></div>
        {_gate_panel(record)}
      </div>
      <form class="composer" method="post" action="/ask">
        <input type="hidden" name="id" value="{_e(record.id)}">
        <div class="composer-box">
          <textarea name="q" rows="1" placeholder="Ask about the owner, blast radius, rollback, or why this was gated…"></textarea>
          <button class="icon-btn" type="button" data-dictate aria-label="Dictate" aria-pressed="false" title="Dictate">{_ICON_MIC}</button>
          <button type="submit">Ask</button>
        </div>
        <div class="composer-hint">⌘ Enter / Ctrl+Enter to send. Answers are retrieval over this incident package. Questions never change a gate.</div>
      </form>
    </div>
    """


# --------------------------------------------------------------------- approvals


def _approvals_workspace(app: Assent, actor: str, selected_id: Optional[str], scope: str) -> str:
    me = ident.person(actor)
    inbox = _inbox_for(app, actor, scope)
    history = _history_for(app, actor, scope)
    scope_label = "the team" if scope == "team" else (me.short or me.name)

    you_on = "on" if scope == "you" else ""
    team_on = "on" if scope == "team" else ""

    cards = []
    for r in inbox:
        change = r.change
        assignee = _assignee_for(r)
        cmd = f"{change.action.type} → {change.action.target}" if change else "no catalogued action"
        env = change.risk_envelope.environment.value if change else "—"
        blast = str(change.risk_envelope.blast_radius) if change else "—"
        rev = change.risk_envelope.reversibility.value if change else "—"
        owner = change.owner.id if change else "unknown"
        expanded = r.id == selected_id or len(inbox) == 1
        body = f'<div class="acard-body">{_card_for(r)}</div>' if expanded else ""
        href = f"/approvals?c={quote(r.id)}" if not expanded else f"/change/{quote(r.id)}"
        cta = "Open thread" if expanded else "Review"
        cards.append(
            f"""<div class="acard">
              <div class="acard-head">
                <div>
                  <div class="acard-title">{_e(_alert_title(r))}</div>
                  <div class="acard-cmd">{_e(r.id)} · {_e(cmd)}</div>
                </div>
                <div class="signals">
                  {_sev_chip(r)}
                  {_pill_for(r)}
                  <a class="btn btn-secondary" href="{href}">{cta}</a>
                </div>
              </div>
              <div class="acard-meta">
                <div class="mini"><div class="k">Assigned to</div>
                  <div class="v">{ident.identity(assignee, is_self=assignee.id == me.id)}</div></div>
                <div class="mini"><div class="k">Owner of record</div><div class="v">{_e(owner)}</div></div>
                <div class="mini"><div class="k">Environment</div><div class="v">{_e(env)}</div></div>
                <div class="mini"><div class="k">Blast radius</div><div class="v num">{_e(blast)}</div></div>
                <div class="mini"><div class="k">Reversibility</div><div class="v">{_e(rev)}</div></div>
              </div>
              {body}
            </div>"""
        )
    inbox_html = "".join(cards) or (
        f'<div class="empty">Nothing is waiting on {_e(scope_label)}. '
        f'Switch to {"You" if scope == "team" else "Team"} to widen the view.</div>'
    )

    rows = []
    for r in history:
        change = r.change
        decider = ident.resolver(r.resolved_by or "assent")
        cmd = change.action.type if change else r.signal.kind
        target = change.action.target if change else r.signal.target
        env = change.risk_envelope.environment.value if change else "—"
        blast = change.risk_envelope.blast_radius if change else "—"
        rev = change.risk_envelope.reversibility.value if change else "—"
        owner = change.owner.id if change else "unknown"
        why = "; ".join(r.reasons[:2]) if r.reasons else "—"
        when = r.resolved_at.strftime("%b %d · %H:%M:%S") if r.resolved_at else "—"
        rollback = change.rollback if change is not None else "—"
        rows.append(
            f"""<tr>
              <td><a class="strong" href="/change/{quote(r.id)}">{_e(_titlecase_action(cmd))}</a>
                  <div class="muted"><code>{_e(r.id)}</code></div></td>
              <td><code>{_e(target)}</code>
                  <div class="muted">{_e(env)} · blast {_e(str(blast))} · {_e(rev)}</div></td>
              <td>{_pill_for(r)}<div class="muted">{_e(_STATE_LABEL.get(r.state, r.state.value))}</div></td>
              <td>{ident.identity(decider, is_self=decider.id == me.id, compact=True)}
                  <div class="muted" style="margin-top:4px">{_e(when)}</div></td>
              <td>{_e(owner)}</td>
              <td class="why">{_e(why)}</td>
              <td class="why">{_e(rollback)}</td>
            </tr>"""
        )
    table = "\n".join(rows) or (
        f'<tr><td colspan="7" class="muted" style="padding:28px; text-align:center">'
        f'No decisions recorded for {_e(scope_label)} yet.</td></tr>'
    )

    ok, message = app.ledger.verify()
    integrity = (
        f'<div class="footnote ok">Hash chain verified across {len(app.ledger)} entries.</div>'
        if ok
        else f'<div class="footnote bad">Hash chain broken — {_e(message)}</div>'
    )

    auto = app.stats().get("auto_executed", 0)
    return f"""
    <div class="page"><div class="page-inner">
      <div class="page-head">
        <div>
          <h1>Approvals</h1>
          <p class="lede">Every write is routed to a named, authoritative human — never a
          shared queue. Audit follows the same scope you are viewing.</p>
        </div>
        <form class="segment" method="post" action="/scope">
          <input type="hidden" name="next" value="/approvals">
          <button class="{you_on}" type="submit" name="scope" value="you">You</button>
          <button class="{team_on}" type="submit" name="scope" value="team">Team</button>
        </form>
      </div>

      <div class="stats">
        <div class="stat route"><div class="n">{len(inbox)}</div><div class="l">awaiting {_e(scope_label)}</div></div>
        <div class="stat auto"><div class="n">{auto}</div><div class="l">auto-assented by policy</div></div>
        <div class="stat"><div class="n">{len(history)}</div><div class="l">decisions on record</div></div>
      </div>

      <details class="fold" data-fold="inbox" open>
        <summary><h2>Inbox</h2><span class="note">{len(inbox)} waiting · click to collapse</span></summary>
        <div class="fold-body"><div class="cards">{inbox_html}</div></div>
      </details>

      <details class="fold" data-fold="audit" open>
        <summary><h2>Audit</h2><span class="note">command · envelope · decider · why · rollback</span></summary>
        <div class="fold-body">
          <div class="tbl-wrap">
            <table class="tbl">
              <thead><tr>
                <th>Action</th><th>Target &amp; envelope</th><th>Outcome</th>
                <th>Decided by</th><th>Owner of record</th><th>Why the engine gated</th><th>Rollback</th>
              </tr></thead>
              <tbody>{table}</tbody>
            </table>
          </div>
          {integrity}
        </div>
      </details>
    </div></div>
    """


# --------------------------------------------------------------------- infra


def _infra_workspace(app: Assent, selected_id: Optional[str]) -> str:
    agents = roster_for(app)
    selected_sys = None
    if selected_id:
        try:
            selected_sys = app.require(selected_id).signal.target
        except KeyError:
            selected_sys = None

    items = []
    for a in agents:
        p = ident.agent(a.role.value) or ident.AGENTS["assent"]
        items.append(
            f"""<div class="roster-item">
              {ident.avatar(p, size="sm")}
              <span class="byline stack">
                <span class="byline-name">{_e(p.name)}</span>
                <span class="detail">{_e(a.detail)}</span>
              </span>
              <span class="status-dot dot-{a.status.value}" title="{_e(a.status.value)}"></span>
            </div>"""
        )

    return f"""
    <div class="infra"><div class="infra-inner">
      <div class="page-head">
        <div>
          <h1>Infrastructure</h1>
          <p class="lede">A map of systems Assent can act on. A mark on a node is an
          open change; a dot means an agent is on it. Click through to the thread.</p>
        </div>
      </div>
      <div class="roster">{''.join(items)}</div>
      {render_topology(app, agents, selected=selected_sys)}
    </div></div>
    """


# --------------------------------------------------------------------- entry


def render_app(
    app: Assent,
    *,
    actor: str,
    profile: str,
    tool: str = "chat",
    selected_id: Optional[str] = None,
    extras: Optional[Sequence[dict]] = None,
    scope: str = "you",
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
        workspace = _approvals_workspace(app, actor, selected_id, scope)
        crumb = "Approvals <strong>·</strong> " + ("Team" if scope == "team" else "You")
    elif tool == "infra":
        workspace = _infra_workspace(app, selected_id)
        crumb = f"Infrastructure <strong>·</strong> {len(app.inventory.names())} systems"
    else:
        workspace = _thread_workspace(selected, extras)
        crumb = "Threads" + (f" <strong>·</strong> {_e(selected.id)}" if selected else "")

    return _shell(
        app=app,
        tool=tool,
        actor=actor,
        profile=profile,
        selected_id=selected_id,
        workspace=workspace,
        crumb=crumb,
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
        app, actor=actor, profile=profile, tool="chat",
        selected_id=record.id, extras=extras,
    )


def render_overview(app: Assent, *, actor: str, profile: str) -> str:
    return render_app(app, actor=actor, profile=profile, tool="infra")


def render_ledger_page(app: Assent, *, actor: str, profile: str) -> str:
    """Route alias — the useful surface is Approvals → Audit, not a hash log."""
    return render_app(app, actor=actor, profile=profile, tool="approvals")
