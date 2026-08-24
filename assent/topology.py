"""Infrastructure map — a quiet schematic, not a cartoon lab.

Zones are rooms with hairline walls. Systems are plates. An open change is a
left mark on the node; agents working it are a small status dot. Click a
system to open its thread.
"""

from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence, Tuple

from assent.agents import AgentView
from assent.inventory import Inventory
from assent.runtime import Assent, ChangeRecord

_e = html.escape

_NW, _NH = 148.0, 66.0
_HW, _HH = _NW / 2, _NH / 2

_LABELS: Dict[str, str] = {
    "internet": "Internet",
    "staging-edge-fw": "Edge Firewall",
    "stg-access-sw": "Access Switch",
    "laptop-4471": "Laptop 4471",
    "payments-staging-api": "Payments",
    "prod-core-sw": "Core Switch",
    "auth-service": "Auth Service",
    "payments-api": "Payments API",
    "analytics-worker": "Analytics",
    "payments-latency": "Latency Probe",
    "dev-sandbox-07": "Dev Sandbox",
}

# Coordinates are plate centers. Keep ≥24px padding inside each zone.
_FABRIC: Tuple[dict, ...] = (
    {"id": "internet", "kind": "cloud", "zone": "wan", "x": 600, "y": 86},
    {"id": "staging-edge-fw", "kind": "firewall", "zone": "edge", "x": 600, "y": 214},
    {"id": "stg-access-sw", "kind": "switch", "zone": "staging", "x": 180, "y": 368},
    {"id": "laptop-4471", "kind": "endpoint", "zone": "staging", "x": 112, "y": 512},
    {"id": "payments-staging-api", "kind": "service", "zone": "staging", "x": 248, "y": 512},
    {"id": "prod-core-sw", "kind": "switch", "zone": "prod", "x": 600, "y": 368},
    {"id": "auth-service", "kind": "service", "zone": "prod", "x": 468, "y": 512},
    {"id": "payments-api", "kind": "service", "zone": "prod", "x": 600, "y": 512},
    {"id": "analytics-worker", "kind": "service", "zone": "prod", "x": 732, "y": 512},
    {"id": "payments-latency", "kind": "service", "zone": "prod", "x": 600, "y": 628},
    {"id": "dev-sandbox-07", "kind": "service", "zone": "dev", "x": 1020, "y": 430},
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

_ZONES: Tuple[dict, ...] = (
    {"id": "wan", "label": "WAN", "x": 470, "y": 28, "w": 260, "h": 116},
    {"id": "edge", "label": "Edge", "x": 470, "y": 156, "w": 260, "h": 116},
    {"id": "staging", "label": "Staging", "x": 28, "y": 300, "w": 308, "h": 280},
    {"id": "prod", "label": "Production", "x": 352, "y": 300, "w": 496, "h": 392},
    {"id": "dev", "label": "Development", "x": 864, "y": 300, "w": 312, "h": 220},
)

_SEV_COLOR = {
    "critical": "#a13232",
    "high": "#8a5a0f",
    "medium": "#565652",
    "low": "#17714a",
}


def _caption(node_id: str) -> str:
    return _LABELS.get(node_id, node_id.replace("-", " ").title())


def _index() -> Dict[str, dict]:
    return {n["id"]: n for n in _FABRIC}


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


def _mark(kind: str, color: str) -> str:
    """Tiny geometric mark — stroke only, sits in the left of the plate."""
    s = f'stroke="{color}" fill="none" stroke-width="1.35" stroke-linejoin="round" stroke-linecap="round"'
    if kind == "cloud":
        return f'<path {s} d="M-3 6h11a5 5 0 0 0 0-10 6.2 6.2 0 0 0-12 1.2A4.4 4.4 0 0 0-3 6z"/>'
    if kind == "firewall":
        return (
            f'<rect {s} x="-8" y="-7" width="16" height="14" rx="2"/>'
            f'<path {s} d="M-5 -3h10M-5 0h10M-5 3h10"/>'
        )
    if kind == "switch":
        return (
            f'<rect {s} x="-9" y="-5" width="18" height="10" rx="2"/>'
            f'<path {s} d="M-5 -2v4M-1 -2v4M3 -2v4M7 -2v4"/>'
        )
    if kind == "endpoint":
        return (
            f'<rect {s} x="-8" y="-7" width="16" height="11" rx="1.6"/>'
            f'<path {s} d="M-3 7h6"/>'
        )
    return f'<rect {s} x="-7" y="-8" width="14" height="16" rx="2.2"/>'


def _ports(a: dict, b: dict) -> Tuple[float, float, float, float]:
    ax, ay, bx, by = a["x"], a["y"], b["x"], b["y"]
    if by > ay + 24:
        return ax, ay + _HH, bx, by - _HH
    if ay > by + 24:
        return ax, ay - _HH, bx, by + _HH
    if bx > ax:
        return ax + _HW, ay, bx - _HW, by
    return ax - _HW, ay, bx + _HW, by


def _elbow(x1: float, y1: float, x2: float, y2: float) -> str:
    if abs(x1 - x2) < 0.8:
        return f"M{x1:.1f},{y1:.1f}V{y2:.1f}"
    if abs(y1 - y2) < 0.8:
        return f"M{x1:.1f},{y1:.1f}H{x2:.1f}"
    mid = (y1 + y2) / 2
    return f"M{x1:.1f},{y1:.1f}V{mid:.1f}H{x2:.1f}V{y2:.1f}"


def _meta_line(node_id: str, inventory: Inventory, app: Assent) -> str:
    sys = inventory.lookup(node_id)
    bits: List[str] = []
    if sys is not None:
        bits.append({"dev": "Development", "staging": "Staging", "prod": "Production"}[sys.environment.value])
        if sys.tier0:
            bits.append("Tier 0")
    else:
        bits.append({
            "internet": "WAN",
            "stg-access-sw": "Staging",
            "prod-core-sw": "Production",
        }.get(node_id, "Fabric"))
    owner = app.graph.resolve(node_id)
    if owner.id != "unknown":
        bits.append(owner.id)
    return " · ".join(bits)


def _severity(record: Optional[ChangeRecord]) -> str:
    if record is None:
        return ""
    sev = (record.signal.severity or "medium").lower()
    return sev if sev in _SEV_COLOR else "medium"


def _node(
    node: dict,
    *,
    inventory: Inventory,
    app: Assent,
    pins: Dict[str, List[dict]],
    open_by_target: Dict[str, List[ChangeRecord]],
    href_for: Dict[str, str],
    selected: Optional[str],
) -> str:
    node_id = node["id"]
    recs = open_by_target.get(node_id) or []
    rec = recs[0] if recs else None
    sev = _severity(rec)
    href = href_for.get(node_id, "")
    on = " on" if node_id == selected else ""
    hot = " hot" if rec else ""
    ink = "#0d5c56" if rec else "#3a4248"
    accent = _SEV_COLOR.get(sev, "")
    name = _caption(node_id)
    meta = _meta_line(node_id, inventory, app)

    accent_rect = ""
    if accent:
        accent_rect = (
            f'<rect class="node-accent" x="{-_HW}" y="{-_HH + 8}" width="3.5" height="{_NH - 16}" '
            f'rx="1.5" fill="{accent}"/>'
        )

    agents = pins.get(node_id) or []
    seen = []
    for pin in agents:
        if pin["name"] in seen:
            continue
        seen.append(pin["name"])
    agent_title = _e(" · ".join(f"{p['name']} ({p['note']})" for p in agents[:3]))
    status = agents[0]["status"] if agents else ""
    dot_fill = {"working": "#8a5a0f", "blocked": "#a13232", "complete": "#17714a"}.get(status, "")
    live = ""
    if dot_fill:
        live = (
            f'<circle class="node-live" cx="{_HW - 12}" cy="{-_HH + 12}" r="3.5" '
            f'fill="{dot_fill}"><title>{agent_title}</title></circle>'
        )

    inner = f"""
      <rect class="node-plate" x="{-_HW}" y="{-_HH}" width="{_NW}" height="{_NH}" rx="12"/>
      {accent_rect}
      <g transform="translate({-_HW + 18},{-2})">{_mark(node['kind'], ink)}</g>
      <text class="node-name" x="{-_HW + 38}" y="-2">{_e(name)}</text>
      <text class="node-meta" x="{-_HW + 38}" y="14">{_e(meta)}</text>
      {live}
    """
    tag = "a" if href else "g"
    href_attr = f' href="{_e(href)}"' if href else ""
    return (
        f'<{tag} class="node{on}{hot}{"" if href else " muted"}"{href_attr} '
        f'transform="translate({node["x"]},{node["y"]})">{inner}</{tag}>'
    )


def render_topology(
    app: Assent,
    agents: Sequence[AgentView],
    *,
    selected: Optional[str] = None,
) -> str:
    inventory: Inventory = app.inventory
    pins = pins_for(app, agents)
    nodes = _index()
    open_by_target: Dict[str, List[ChangeRecord]] = {}
    for record in app.queue():
        open_by_target.setdefault(record.signal.target, []).append(record)
    href_for: Dict[str, str] = {}
    for record in app.queue():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")
    for record in app.records():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")
    open_targets = set(open_by_target)

    zones = []
    for z in _ZONES:
        zones.append(
            f"""<g class="topo-zone">
              <rect x="{z['x']}" y="{z['y']}" width="{z['w']}" height="{z['h']}" rx="16"/>
              <text x="{z['x'] + 16}" y="{z['y'] + 22}">{_e(z['label'])}</text>
            </g>"""
        )

    links = []
    for a_id, b_id in _LINKS:
        a, b = nodes[a_id], nodes[b_id]
        x1, y1, x2, y2 = _ports(a, b)
        hot = a_id in open_targets or b_id in open_targets
        cls = "topo-link hot" if hot else "topo-link"
        links.append(f'<path class="{cls}" d="{_elbow(x1, y1, x2, y2)}"/>')

    plates = [
        _node(
            node,
            inventory=inventory,
            app=app,
            pins=pins,
            open_by_target=open_by_target,
            href_for=href_for,
            selected=selected,
        )
        for node in _FABRIC
    ]

    legend = """
    <g class="topo-legend" transform="translate(32,708)">
      <rect class="node-accent" x="0" y="-6" width="3.5" height="12" rx="1.5" fill="#a13232"/>
      <text x="12" y="3">Open change</text>
      <circle cx="118" cy="0" r="3.5" fill="#8a5a0f"/>
      <text x="128" y="3">Agent on this system</text>
      <path class="topo-link" d="M268,-0.5 H308"/>
      <text x="316" y="3">Path</text>
    </g>
    """

    return f"""
    <div class="fabric">
      <svg class="topo" viewBox="0 0 1200 740" role="img" aria-label="Infrastructure map">
        {''.join(zones)}
        {''.join(links)}
        {''.join(plates)}
        {legend}
      </svg>
    </div>
    """
