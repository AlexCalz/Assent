"""The Assent web app — the product you can actually operate.

    python -m assent.app          # then open http://127.0.0.1:8000

Serves the approval queue over HTTP with working controls: approve, deny, and undo all
drive the real ``Assent`` runtime, so every click moves a change through the same
deterministic gate the library enforces. ``/ledger`` shows the tamper-evident audit
trail and re-verifies the hash chain on every load.

Standard library only (``http.server``), consistent with the rest of the package: no
install step, nothing to provision, `python -m assent.app` and it runs.
"""

from __future__ import annotations

import argparse
import html
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from assent.approval_card import _PAGE_CSS, render_card
from assent.change import Environment
from assent.inventory import Inventory, SystemRecord
from assent.graph import OwnershipClaim, OwnershipGraph, Source
from assent.policy import PolicyResult
from assent.proposer import Signal
from assent.runtime import Assent, ChangeRecord, ChangeState

_e = html.escape

# How each state should read to a human, and what control the card offers.
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


APP_CSS = """
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px;
  flex-wrap: wrap; margin-bottom: 22px; }
.topbar nav { display: flex; gap: 8px; }
.topbar nav a { font-size: 13.5px; font-weight: 600; color: var(--ink-soft);
  text-decoration: none; padding: 7px 13px; border-radius: 8px; border: 1px solid var(--border); }
.topbar nav a:hover { background: var(--surface-2); color: var(--ink); }
.topbar nav a.on { background: var(--surface); color: var(--ink); border-color: var(--border-strong); }
.who { font-size: 13px; color: var(--ink-faint); }
.who strong { color: var(--ink); }

.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 26px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 11px;
  padding: 13px 15px; box-shadow: var(--shadow); }
.tile .n { font-size: 25px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.tile .l { font-size: 12px; color: var(--ink-faint); margin-top: 1px; }
.tile.awaiting .n { color: var(--route); }
.tile.auto .n { color: var(--auto); }

h2.sec { font-size: 15px; letter-spacing: 0.01em; margin: 30px 0 12px;
  color: var(--ink-soft); font-weight: 650; }
h2.sec:first-of-type { margin-top: 0; }
.empty { background: var(--surface); border: 1px dashed var(--border-strong); border-radius: 12px;
  padding: 22px; text-align: center; color: var(--ink-faint); font-size: 14px; }

.triage { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--border-strong);
  border-radius: 13px; padding: 18px 20px; box-shadow: var(--shadow); }
.triage h3 { margin: 8px 0 3px; font-family: var(--mono); font-size: 16px; }
.triage p { margin: 0; font-size: 14px; color: var(--ink-soft); }
.triage .actions { margin-top: 14px; }

table.ledger { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.ledger th { text-align: left; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--ink-faint); padding: 8px 10px; border-bottom: 1px solid var(--border); }
table.ledger td { padding: 9px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
table.ledger tr:last-child td { border-bottom: none; }
table.ledger .mono { font-family: var(--mono); font-size: 12.5px; }
.ledger-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  overflow-x: auto; box-shadow: var(--shadow); }
.chain { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; font-size: 13.5px; }
.chain .ok { color: var(--auto); font-weight: 650; }
.chain .bad { color: var(--escalate); font-weight: 650; }
.kind { font-weight: 650; }
.kind-executed, .kind-approved { color: var(--auto); }
.kind-denied, .kind-failed { color: var(--escalate); }
.kind-rolled_back { color: var(--route); }
@media (max-width: 620px) { .tiles { grid-template-columns: repeat(2, 1fr); } }
"""


def _shell(body: str, *, page: str, actor: str) -> str:
    def nav(href: str, label: str, key: str) -> str:
        return f'<a href="{href}" class="{"on" if page == key else ""}">{label}</a>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Assent — control plane</title>
<style>{_PAGE_CSS}{APP_CSS}</style>
</head>
<body>
  <main class="wrap">
    <div class="topbar">
      <div>
        <div class="brand">Assent</div>
        <div class="who">acting as <strong>{_e(actor)}</strong></div>
      </div>
      <nav>{nav('/', 'Queue', 'queue')}{nav('/ledger', 'Audit ledger', 'ledger')}</nav>
    </div>
{body}
  </main>
</body>
</html>
"""


def _triage_card(record: ChangeRecord) -> str:
    reason = record.reasons[0] if record.reasons else "no proposal could be made"
    return f"""
      <div class="triage">
        <div class="verdict">
          <span class="pill pill-route">Needs triage</span>
          <span class="badge badge-state">no automated proposal</span>
          <span class="rec-id">{_e(record.id)}</span>
        </div>
        <h3>{_e(record.signal.kind)} → {_e(record.signal.target)}</h3>
        <p>{_e(reason)}</p>
        <p class="muted" style="margin-top:6px">Reported by {_e(record.signal.source)}
           · severity {_e(record.signal.severity)}</p>
        <footer class="actions">
          <form method="post" action="/deny"><input type="hidden" name="id" value="{_e(record.id)}">
            <button class="btn btn-secondary" type="submit">Dismiss</button></form>
        </footer>
      </div>
    """


def _record_card(record: ChangeRecord) -> str:
    if record.change is None:
        return _triage_card(record)
    return render_card(
        record.change,
        PolicyResult(record.decision, record.reasons),
        record.audit,
        record_id=record.id,
        state_label=_STATE_LABEL.get(record.state, record.state.value),
        controls=_STATE_CONTROLS.get(record.state, ""),
    )


def render_queue(app: Assent, actor: str) -> str:
    stats = app.stats()
    awaiting = len(app.queue())
    auto = stats[ChangeState.AUTO_EXECUTED.value]
    executed = auto + stats[ChangeState.EXECUTED.value]

    queue_cards = "\n".join(_record_card(r) for r in app.queue()) or (
        '<div class="empty">Nothing is waiting on a human right now.</div>'
    )
    settled_cards = "\n".join(_record_card(r) for r in app.settled()) or (
        '<div class="empty">No changes have been settled yet.</div>'
    )

    body = f"""
    <div class="tiles">
      <div class="tile awaiting"><div class="n">{awaiting}</div><div class="l">awaiting a human</div></div>
      <div class="tile auto"><div class="n">{auto}</div><div class="l">auto-executed</div></div>
      <div class="tile"><div class="n">{executed}</div><div class="l">changes applied</div></div>
      <div class="tile"><div class="n">{stats['total']}</div><div class="l">signals handled</div></div>
    </div>

    <h2 class="sec">Waiting on you</h2>
    <div class="queue">{queue_cards}</div>

    <h2 class="sec">Settled</h2>
    <div class="queue">{settled_cards}</div>
    """
    return _shell(body, page="queue", actor=actor)


def render_ledger(app: Assent, actor: str) -> str:
    ok, message = app.ledger.verify()
    rows = "\n".join(
        f"""<tr>
          <td class="mono">{entry.seq}</td>
          <td class="mono">{entry.at.strftime('%H:%M:%S')}</td>
          <td><span class="kind kind-{_e(entry.kind)}">{_e(entry.kind)}</span></td>
          <td class="mono">{_e(entry.change_id)}</td>
          <td>{_e(entry.actor)}</td>
          <td class="mono">{_e(_summarize(entry.detail))}</td>
          <td class="mono muted">{_e(entry.entry_hash[:10])}…</td>
        </tr>"""
        for entry in reversed(app.ledger.entries())
    ) or '<tr><td colspan="7" style="text-align:center;color:var(--ink-faint)">No entries yet.</td></tr>'

    body = f"""
    <h2 class="sec">Audit ledger</h2>
    <div class="chain">
      <span class="{'ok' if ok else 'bad'}">{'✓ chain verified' if ok else '✕ chain broken'}</span>
      <span class="muted">{_e(message)}</span>
    </div>
    <div class="ledger-wrap">
      <table class="ledger">
        <thead><tr><th>#</th><th>Time</th><th>Event</th><th>Change</th><th>Actor</th>
          <th>Detail</th><th>Hash</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """
    return _shell(body, page="ledger", actor=actor)


def _summarize(detail: dict) -> str:
    parts = []
    for key, value in detail.items():
        if key == "reasons":
            continue
        if isinstance(value, float):
            value = f"{value:.2f}"
        parts.append(f"{key}={value}")
    return ", ".join(parts)[:120] or "—"


# --------------------------------------------------------------------- demo world


def demo_app(now: Optional[datetime] = None) -> Assent:
    """A small, realistic world so the app has something to show on first run."""
    now = now or datetime.now(timezone.utc)

    inventory = Inventory()
    inventory.add(SystemRecord("staging-edge-fw", Environment.STAGING, dependents=0))
    inventory.add(SystemRecord("dev-sandbox-07", Environment.DEV, dependents=0))
    inventory.add(SystemRecord("payments-api", Environment.PROD, tier0=True, dependents=4))
    inventory.add(SystemRecord("laptop-4471", Environment.STAGING, dependents=0))
    inventory.add(SystemRecord("analytics-worker", Environment.PROD, dependents=2))

    graph = OwnershipGraph()
    graph.add(OwnershipClaim("staging-edge-fw", "team-netsec", Source.CODE, now))
    graph.add(OwnershipClaim("staging-edge-fw", "team-netsec", Source.OPS, now))
    graph.add(OwnershipClaim("payments-api", "team-payments", Source.CODE, now))
    graph.add(OwnershipClaim("laptop-4471", "team-endpoint", Source.OPS, now))
    graph.add(OwnershipClaim("analytics-worker", "team-data", Source.CLOUD, now))
    # dev-sandbox-07 deliberately has no owner on file.

    app = Assent(inventory=inventory, graph=graph)

    app.submit(Signal("malicious_domain", "staging-edge-fw",
                      summary="Egress to a known C2 domain.",
                      indicators={"domain": "c2.evil.example"}, source="dns-sensor",
                      severity="high"), now=now)
    app.submit(Signal("leaked_credential", "payments-api",
                      summary="API key found in a public paste.",
                      indicators={"key_id": "AKIA…7Q2"}, source="secret-scanner",
                      severity="critical"), now=now)
    app.submit(Signal("c2_beacon", "laptop-4471",
                      summary="Periodic beaconing to an unclassified host.",
                      indicators={"interval_s": "60"}, source="edr", severity="high"), now=now)
    app.submit(Signal("overprivileged_role", "analytics-worker",
                      summary="Role grants org-wide write access.",
                      indicators={"role": "analytics-writer"}, source="cspm",
                      severity="medium"), now=now)
    app.submit(Signal("ransomware_precursor", "dev-sandbox-07",
                      summary="Shadow-copy deletion observed; no playbook exists.",
                      indicators={"process": "vssadmin.exe"}, source="edr",
                      severity="critical"), now=now)
    return app


# --------------------------------------------------------------------- server


class _Handler(BaseHTTPRequestHandler):
    app: Assent
    actor: str

    def log_message(self, fmt, *args):  # quieter console
        pass

    def _send(self, body: str, status: int = 200) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, to: str = "/") -> None:
        self.send_response(303)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send(render_queue(self.app, self.actor))
        elif path == "/ledger":
            self._send(render_ledger(self.app, self.actor))
        else:
            self._send(_shell('<div class="empty">Not found.</div>',
                              page="", actor=self.actor), status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}
        change_id = (form.get("id") or [""])[0]

        try:
            if path == "/approve":
                self.app.approve(change_id, actor=self.actor)
            elif path == "/deny":
                self.app.deny(change_id, actor=self.actor)
            elif path == "/rollback":
                self.app.rollback(change_id, actor=self.actor)
            else:
                self._send(_shell('<div class="empty">Not found.</div>',
                                  page="", actor=self.actor), status=404)
                return
        except (KeyError, ValueError):
            # Stale form (already acted on, or unknown id) — just re-render current state.
            pass
        self._redirect("/")


def serve(app: Assent, host: str = "127.0.0.1", port: int = 8000, actor: str = "you") -> None:
    handler = type("Handler", (_Handler,), {"app": app, "actor": actor})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Assent running at http://{host}:{port}  (acting as {actor})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Assent control plane.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--actor", default="you", help="who approvals are recorded as")
    args = parser.parse_args()
    serve(demo_app(), host=args.host, port=args.port, actor=args.actor)


if __name__ == "__main__":
    main()
