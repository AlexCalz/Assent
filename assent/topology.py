"""Infrastructure inventory — systems grouped by environment.

A professional control-plane surface: lanes of systems, not a cartoon network
diagram. Open changes and the agents working them sit on the row.
"""

from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence, Tuple

from assent.agents import AgentView
from assent.inventory import Inventory
from assent.runtime import Assent, ChangeRecord

_e = html.escape

_LABELS: Dict[str, Tuple[str, str]] = {
    "internet": ("Internet", "WAN"),
    "staging-edge-fw": ("Edge Firewall", "Edge"),
    "stg-access-sw": ("Access Switch", "Staging"),
    "laptop-4471": ("Laptop 4471", "Endpoint"),
    "payments-staging-api": ("Payments", "Staging"),
    "prod-core-sw": ("Core Switch", "Production"),
    "auth-service": ("Auth Service", "Identity"),
    "payments-api": ("Payments API", "Production"),
    "analytics-worker": ("Analytics", "Production"),
    "payments-latency": ("Latency Probe", "Production"),
    "dev-sandbox-07": ("Dev Sandbox", "Development"),
}

_FABRIC: Tuple[dict, ...] = (
    {"id": "internet", "kind": "edge", "zone": "wan"},
    {"id": "staging-edge-fw", "kind": "firewall", "zone": "edge"},
    {"id": "stg-access-sw", "kind": "switch", "zone": "staging"},
    {"id": "laptop-4471", "kind": "endpoint", "zone": "staging"},
    {"id": "payments-staging-api", "kind": "service", "zone": "staging"},
    {"id": "prod-core-sw", "kind": "switch", "zone": "prod"},
    {"id": "auth-service", "kind": "service", "zone": "prod"},
    {"id": "payments-api", "kind": "service", "zone": "prod"},
    {"id": "analytics-worker", "kind": "service", "zone": "prod"},
    {"id": "payments-latency", "kind": "service", "zone": "prod"},
    {"id": "dev-sandbox-07", "kind": "service", "zone": "dev"},
)

_LINKS: Tuple[Tuple[str, str], ...] = (
    ("internet", "staging-edge-fw"),
    ("staging-edge-fw", "stg-access-sw"),
    ("stg-access-sw", "laptop-4471"),
    ("stg-access-sw", "payments-staging-api"),
    ("staging-edge-fw", "prod-core-sw"),
    ("staging-edge-fw", "dev-sandbox-07"),
    ("prod-core-sw", "auth-service"),
    ("prod-core-sw", "payments-api"),
    ("prod-core-sw", "analytics-worker"),
    ("payments-api", "payments-latency"),
)

_LANES: Tuple[Tuple[str, str], ...] = (
    ("wan", "WAN"),
    ("edge", "Edge"),
    ("staging", "Staging"),
    ("prod", "Production"),
    ("dev", "Development"),
)

_KIND = {
    "edge": "edge",
    "firewall": "firewall",
    "switch": "switch",
    "endpoint": "endpoint",
    "service": "service",
}


def _caption(node_id: str) -> str:
    return _LABELS.get(node_id, (node_id.replace("-", " ").title(), "Fabric"))[0]


def _parents() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for a, b in _LINKS:
        out.setdefault(b, []).append(a)
    return out


def pins_for(app: Assent, agents: Sequence[AgentView]) -> Dict[str, List[dict]]:
    open_by_target: Dict[str, List[ChangeRecord]] = {}
    for record in app.queue():
        open_by_target.setdefault(record.signal.target, []).append(record)

    pins: Dict[str, List[dict]] = {}

    def add(system: str, agent: AgentView, note: str) -> None:
        pins.setdefault(system, []).append(
            {
                "role": agent.role.value,
                "name": agent.name,
                "status": agent.status.value,
                "note": note,
            }
        )

    for agent in agents:
        if agent.status.value == "idle":
            continue
        if agent.role.value == "proposer":
            for rec in app.queue():
                if rec.change is None:
                    add(rec.signal.target, agent, "needs a playbook")
        elif agent.role.value == "ownership":
            for rec in app.queue():
                if rec.change is not None and rec.state.value == "pending_approval":
                    add(rec.signal.target, agent, "routing to owner")
        elif agent.role.value == "auditor":
            for rec in app.queue():
                if rec.state.value == "escalated":
                    add(rec.signal.target, agent, "second opinion / dissent")
        else:
            for rec in app.queue():
                add(rec.signal.target, agent, "gate held for human")

    for target, recs in open_by_target.items():
        if target not in pins:
            pins[target] = [
                {
                    "role": "policy",
                    "name": "Policy Engine",
                    "status": "working",
                    "note": f"{len(recs)} open change(s)",
                }
            ]
    return pins


def _open_signals(record: ChangeRecord) -> str:
    sev = (record.signal.severity or "medium").lower()
    if sev not in {"critical", "high", "medium", "low"}:
        sev = "medium"
    label = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}[sev]
    gate = "triage"
    key = "triage"
    if record.decision is not None:
        raw = record.decision.value
        key = {"auto": "auto", "route_to_owner": "route", "escalate": "escalate"}.get(raw, "triage")
        gate = {"auto": "auto", "route": "needs owner", "escalate": "escalated", "triage": "triage"}[key]
    return (
        f'<span class="sev sev-{_e(sev)}">{label}</span>'
        f'<span class="pill pill-{key}">{gate}</span>'
    )


def _sys_row(
    node: dict,
    *,
    inventory: Inventory,
    app: Assent,
    pins: Dict[str, List[dict]],
    open_by_target: Dict[str, List[ChangeRecord]],
    href_for: Dict[str, str],
    parents: Dict[str, List[str]],
    selected: Optional[str],
) -> str:
    node_id = node["id"]
    name = _caption(node_id)
    recs = open_by_target.get(node_id) or []
    href = href_for.get(node_id, "")
    on = " on" if node_id == selected else ""
    muted = "" if href else " muted"

    meta_bits = [_KIND.get(node["kind"], node["kind"])]
    sys = inventory.lookup(node_id)
    if sys is not None:
        if sys.tier0:
            meta_bits.append("tier 0")
        meta_bits.append(f"blast {sys.blast_radius}")
    owner = app.graph.resolve(node_id)
    if owner.id != "unknown":
        meta_bits.append(owner.id)
    else:
        meta_bits.append("unowned")
    via = parents.get(node_id) or []
    if via:
        meta_bits.append("via " + _caption(via[0]))
    meta_bits.append(node_id)

    live = ""
    if recs:
        live = f'<div class="sys-live">{_open_signals(recs[0])}</div>'

    agent_bits = []
    seen = set()
    for pin in pins.get(node_id, []):
        if pin["name"] in seen:
            continue
        seen.add(pin["name"])
        agent_bits.append(_e(pin["name"]))
    agents = (
        f'<div class="sys-agents">{_e(" · ".join(agent_bits))}</div>' if agent_bits else ""
    )

    inner = f"""
      <div class="sys-name">{_e(name)}</div>
      <div class="sys-meta">{_e(" · ".join(meta_bits))}</div>
      {live}
      {agents}
    """
    if href:
        return f'<a class="sys{on}" href="{_e(href)}">{inner}</a>'
    return f'<div class="sys{muted}{on}">{inner}</div>'


def render_topology(
    app: Assent,
    agents: Sequence[AgentView],
    *,
    selected: Optional[str] = None,
) -> str:
    inventory: Inventory = app.inventory
    pins = pins_for(app, agents)
    parents = _parents()
    open_by_target: Dict[str, List[ChangeRecord]] = {}
    for record in app.queue():
        open_by_target.setdefault(record.signal.target, []).append(record)
    href_for: Dict[str, str] = {}
    for record in app.queue():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")
    for record in app.records():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")

    by_zone: Dict[str, List[dict]] = {zid: [] for zid, _ in _LANES}
    for node in _FABRIC:
        by_zone.setdefault(node["zone"], []).append(node)

    lanes = []
    for zid, label in _LANES:
        nodes = by_zone.get(zid) or []
        rows = "".join(
            _sys_row(
                node,
                inventory=inventory,
                app=app,
                pins=pins,
                open_by_target=open_by_target,
                href_for=href_for,
                parents=parents,
                selected=selected,
            )
            for node in nodes
        )
        lanes.append(
            f"""<section class="lane">
              <header class="lane-head">
                <h2>{_e(label)}</h2>
                <span class="note">{len(nodes)}</span>
              </header>
              {rows}
            </section>"""
        )

    return f"""
    <div class="fabric">
      <div class="lanes">{''.join(lanes)}</div>
    </div>
    """
