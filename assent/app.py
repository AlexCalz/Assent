"""The Assent web app — mission control you can actually operate.

    python -m assent.app          # then open http://127.0.0.1:8000

Serves the Trident-inspired dashboard over HTTP with working controls: approve,
deny, undo, demo inject, and dual deploy profiles all drive the real ``Assent``
runtime. Standard library only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from assent.change import Environment
from assent.dashboard import (
    PROFILES,
    render_change,
    render_ledger_page,
    render_mission,
    render_overview,
)
from assent.graph import OwnershipClaim, OwnershipGraph, Source
from assent.inventory import Inventory, SystemRecord
from assent.proposer import Signal
from assent.runtime import Assent

# Backward-compatible aliases used by existing tests / examples.


def render_queue(app: Assent, actor: str, profile: str = "cloud") -> str:
    return render_mission(app, actor=actor, profile=profile)


def render_ledger(app: Assent, actor: str, profile: str = "cloud") -> str:
    return render_ledger_page(app, actor=actor, profile=profile)


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
    inventory.add(SystemRecord("auth-service", Environment.PROD, tier0=True, dependents=6))
    inventory.add(SystemRecord("payments-latency", Environment.PROD, dependents=3))

    graph = OwnershipGraph()
    graph.add(OwnershipClaim("staging-edge-fw", "team-netsec", Source.CODE, now))
    graph.add(OwnershipClaim("staging-edge-fw", "team-netsec", Source.OPS, now))
    graph.add(OwnershipClaim("payments-api", "team-payments", Source.CODE, now))
    graph.add(OwnershipClaim("laptop-4471", "team-endpoint", Source.OPS, now))
    graph.add(OwnershipClaim("analytics-worker", "team-data", Source.CLOUD, now))
    graph.add(OwnershipClaim("auth-service", "team-identity", Source.CODE, now))
    graph.add(OwnershipClaim("auth-service", "team-identity", Source.OPS, now))
    # dev-sandbox-07 deliberately has no owner on file.

    app = Assent(inventory=inventory, graph=graph)
    _seed_baseline(app, now)
    return app


def _seed_baseline(app: Assent, now: datetime) -> None:
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
                      indicators={"interval_s": "60", "ip": "203.0.113.77"}, source="edr",
                      severity="high"), now=now)
    app.submit(Signal("overprivileged_role", "analytics-worker",
                      summary="Role grants org-wide write access.",
                      indicators={"role": "analytics-writer"}, source="cspm",
                      severity="medium"), now=now)
    app.submit(Signal("ransomware_precursor", "dev-sandbox-07",
                      summary="Shadow-copy deletion observed; no playbook exists.",
                      indicators={"process": "vssadmin.exe"}, source="edr",
                      severity="critical"), now=now)


def inject_demo_scenario(app: Assent, now: Optional[datetime] = None) -> None:
    """Trident-style one-click scenario injection — multi-signal breach narrative."""
    now = now or datetime.now(timezone.utc)
    app.submit(Signal(
        "malicious_domain", "staging-edge-fw",
        summary="Simulated traffic anomaly correlated with C2 domain on payments path.",
        indicators={"domain": "exfil.payments-shadow.example", "metric": "payments.latency_ms"},
        source="telemetry-sentinel", severity="critical",
    ), now=now)
    app.submit(Signal(
        "compromised_session", "auth-service",
        summary="Session tokens reused from anomalous IP after brute-force precursor.",
        indicators={"user": "svc-payments", "ip": "198.51.100.23"},
        source="threat-marshall", severity="high",
    ), now=now)
    app.submit(Signal(
        "c2_beacon", "laptop-4471",
        summary="Endpoint beaconing concurrent with platform CPU spike from heavy search.",
        indicators={"interval_s": "45", "ip": "198.51.100.23"},
        source="platform-auditor", severity="high",
    ), now=now)


# --------------------------------------------------------------------- server


class _Handler(BaseHTTPRequestHandler):
    app: Assent
    actor: str
    profile: str = "cloud"

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

    def _not_found(self) -> None:
        self._send(
            render_mission(self.app, actor=self.actor, profile=self.profile),
            status=404,
        )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send(render_mission(self.app, actor=self.actor, profile=self.profile))
        elif path == "/overview":
            self._send(render_overview(self.app, actor=self.actor, profile=self.profile))
        elif path == "/ledger":
            self._send(render_ledger_page(self.app, actor=self.actor, profile=self.profile))
        elif path.startswith("/change/"):
            change_id = path[len("/change/"):]
            try:
                record = self.app.require(change_id)
            except KeyError:
                self._not_found()
                return
            self._send(render_change(
                self.app, record, actor=self.actor, profile=self.profile,
            ))
        else:
            self._send(
                "<!doctype html><title>Not found</title><p>Not found.</p>",
                status=404,
            )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}
        change_id = (form.get("id") or [""])[0]

        try:
            if path == "/approve":
                self.app.approve(change_id, actor=self.actor)
                self._redirect(f"/change/{change_id}")
                return
            if path == "/deny":
                self.app.deny(change_id, actor=self.actor)
                self._redirect("/")
                return
            if path == "/rollback":
                self.app.rollback(change_id, actor=self.actor)
                self._redirect(f"/change/{change_id}")
                return
            if path == "/demo":
                inject_demo_scenario(self.app)
                self._redirect("/")
                return
            if path == "/profile":
                chosen = (form.get("profile") or ["cloud"])[0]
                if chosen in PROFILES:
                    type(self).profile = chosen
                self._redirect("/")
                return
            self._not_found()
            return
        except (KeyError, ValueError):
            pass
        self._redirect("/")


def serve(
    app: Assent,
    host: str = "127.0.0.1",
    port: int = 8000,
    actor: str = "you",
    profile: str = "cloud",
) -> None:
    handler = type(
        "Handler",
        (_Handler,),
        {"app": app, "actor": actor, "profile": profile},
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Assent running at http://{host}:{port}  (acting as {actor}, profile={profile})")
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
    parser.add_argument(
        "--profile",
        default="cloud",
        choices=sorted(PROFILES),
        help="deployment profile: cloud (startup) or private (agency)",
    )
    args = parser.parse_args()
    serve(
        demo_app(),
        host=args.host,
        port=args.port,
        actor=args.actor,
        profile=args.profile,
    )


if __name__ == "__main__":
    main()
