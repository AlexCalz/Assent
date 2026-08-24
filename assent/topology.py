"""Infrastructure canvas — labeled device plates, not dangling lowercase IDs.

Each node is a plate: icon + title-case name + environment, sized so the
label lives *inside* the box. Zones are rooms; plates never overflow them.
"""

from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence, Tuple

from assent.agents import AgentView
from assent.inventory import Inventory
from assent.runtime import Assent, ChangeRecord

_e = html.escape

# Short, title-case names that fit a 128×86 plate.
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

# Plate is 128×90, so keep coordinates with ≥70px padding inside each zone.
_FABRIC: Tuple[dict, ...] = (
    {"id": "internet", "kind": "cloud", "x": 620, "y": 72, "zone": "wan"},
    {"id": "staging-edge-fw", "kind": "firewall", "x": 620, "y": 188, "zone": "edge"},
    {"id": "stg-access-sw", "kind": "switch", "x": 180, "y": 340, "zone": "staging"},
    {"id": "laptop-4471", "kind": "endpoint", "x": 180, "y": 456, "zone": "staging"},
    {"id": "payments-staging-api", "kind": "server", "x": 180, "y": 572, "zone": "staging"},
    {"id": "prod-core-sw", "kind": "switch", "x": 620, "y": 340, "zone": "prod"},
    {"id": "auth-service", "kind": "identity", "x": 470, "y": 470, "zone": "prod"},
    {"id": "payments-api", "kind": "server", "x": 620, "y": 470, "zone": "prod"},
    {"id": "analytics-worker", "kind": "server", "x": 770, "y": 470, "zone": "prod"},
    {"id": "payments-latency", "kind": "server", "x": 620, "y": 586, "zone": "prod"},
    {"id": "dev-sandbox-07", "kind": "server", "x": 1060, "y": 430, "zone": "dev"},
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
    {"id": "wan", "label": "WAN", "x": 500, "y": 16, "w": 240, "h": 112, "fill": "#eef2f4"},
    {"id": "edge", "label": "Edge", "x": 500, "y": 136, "w": 240, "h": 112, "fill": "#f6efe0"},
    {"id": "staging", "label": "Staging", "x": 36, "y": 268, "w": 288, "h": 372, "fill": "#e8f3ec"},
    {"id": "prod", "label": "Production", "x": 348, "y": 268, "w": 544, "h": 388, "fill": "#f7ecec"},
    {"id": "dev", "label": "Development", "x": 916, "y": 268, "w": 288, "h": 280, "fill": "#e8eef6"},
)

_PLATE_W, _PLATE_H = 128, 90


def _index() -> Dict[str, dict]:
    return {n["id"]: n for n in _FABRIC}


def _caption(node_id: str, inventory: Inventory) -> Tuple[str, str]:
    name, env = _LABELS.get(node_id, (node_id.replace("-", " ").title(), "Fabric"))
    sys = inventory.lookup(node_id)
    if sys is None:
        return name, env
    env = {"dev": "Development", "staging": "Staging", "prod": "Production"}[sys.environment.value]
    if sys.tier0:
        env = env + " · Tier 0"
    return name, env


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


def _icon(kind: str, hot: bool) -> str:
    stroke = "#0d5c56" if hot else "#3a4248"
    fill = "#f3fbf9" if hot else "#ffffff"
    # Compact glyphs that sit in the top half of the plate.
    if kind == "cloud":
        return f"""<g transform="translate(0,-14)">
          <path d="M-22 8 q-7 0 -7 -6 0 -6 7 -6.4 1 -8 9 -8 6 0 8 5 2 -2.6 6 -2.6 6 0 6.6 5.8 6.4.6 6.4 6.2 0 6 -7 6 z"
                fill="{fill}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>
        </g>"""
    if kind == "firewall":
        return f"""<g transform="translate(0,-14)">
          <rect x="-22" y="-12" width="44" height="24" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
          <path d="M-16 -4 H16 M-16 0 H16 M-16 4 H16" stroke="{stroke}" stroke-width="1.3"/>
        </g>"""
    if kind == "switch":
        return f"""<g transform="translate(0,-14)">
          <rect x="-24" y="-9" width="48" height="18" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
          <g fill="{stroke}">
            <rect x="-18" y="-3" width="6" height="6" rx="1"/>
            <rect x="-8" y="-3" width="6" height="6" rx="1"/>
            <rect x="2" y="-3" width="6" height="6" rx="1"/>
            <rect x="12" y="-3" width="6" height="6" rx="1"/>
          </g>
        </g>"""
    if kind == "endpoint":
        return f"""<g transform="translate(0,-14)">
          <rect x="-20" y="-12" width="40" height="22" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
          <rect x="-15" y="-8" width="30" height="13" fill="#17181a"/>
          <rect x="-8" y="11" width="16" height="3" fill="{stroke}"/>
        </g>"""
    if kind == "identity":
        return f"""<g transform="translate(0,-14)">
          <rect x="-16" y="-16" width="32" height="32" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
          <circle cx="0" cy="-4" r="5.5" fill="none" stroke="{stroke}" stroke-width="1.5"/>
          <path d="M-10 12 q10 -12 20 0" fill="none" stroke="{stroke}" stroke-width="1.5"/>
        </g>"""
    return f"""<g transform="translate(0,-14)">
      <rect x="-13" y="-16" width="26" height="32" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
      <rect x="-8" y="-10" width="16" height="4" rx="1" fill="{stroke}" opacity="0.18"/>
      <rect x="-8" y="-3" width="16" height="4" rx="1" fill="{stroke}" opacity="0.18"/>
      <rect x="-8" y="4" width="16" height="4" rx="1" fill="{stroke}" opacity="0.18"/>
      <circle cx="0" cy="12" r="1.8" fill="{stroke}"/>
    </g>"""


def _pin_stack(pins: List[dict]) -> str:
    bits = []
    for i, pin in enumerate(pins[:3]):
        dx = -20 + i * 16
        letter = {"proposer": "P", "ownership": "O", "auditor": "A", "policy": "E"}.get(
            pin["role"], "?"
        )
        title = _e(f"{pin['name']} — {pin['note']}")
        bits.append(
            f"""<g transform="translate({dx},{-52})" class="agent-pin pin-{_e(pin['status'])}">
              <title>{title}</title>
              <circle r="8"/>
              <text text-anchor="middle" dy="3">{letter}</text>
            </g>"""
        )
    return "".join(bits)


def render_topology(
    app: Assent,
    agents: Sequence[AgentView],
    *,
    selected: Optional[str] = None,
) -> str:
    nodes = _index()
    inventory: Inventory = app.inventory
    pins = pins_for(app, agents)
    open_targets = {r.signal.target for r in app.queue()}
    href_for: Dict[str, str] = {}
    for record in app.queue():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")
    for record in app.records():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")

    hw, hh = _PLATE_W / 2, _PLATE_H / 2
    zones = []
    for z in _ZONES:
        zones.append(
            f"""<g class="pt-zone zone-{z['id']}">
              <rect x="{z['x']}" y="{z['y']}" width="{z['w']}" height="{z['h']}" rx="18"
                    fill="{z['fill']}" stroke="rgba(23,24,26,0.08)"/>
              <text x="{z['x'] + 16}" y="{z['y'] + 24}" class="pt-zone-label">{_e(z['label'])}</text>
            </g>"""
        )

    links = []
    for a, b in _LINKS:
        na, nb = nodes[a], nodes[b]
        hot = a in open_targets or b in open_targets
        cls = "pt-link hot" if hot else "pt-link"
        links.append(
            f'<line class="{cls}" x1="{na["x"]}" y1="{na["y"]}" x2="{nb["x"]}" y2="{nb["y"]}"/>'
        )

    devices = []
    for node in _FABRIC:
        name, env = _caption(node["id"], inventory)
        hot = node["id"] in open_targets or node["id"] == selected
        href = href_for.get(node["id"], "")
        on = " on" if node["id"] == selected else ""
        stroke = "#0d5c56" if hot else "rgba(23,24,26,0.12)"
        sw = "2.2" if hot else "1.2"
        fill = "#f4fffb" if hot else "#ffffff"
        inner = f"""
          <rect class="plate" x="{-hw}" y="{-hh}" width="{_PLATE_W}" height="{_PLATE_H}" rx="14"
                fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>
          {_icon(node['kind'], hot)}
          <foreignObject x="{-hw + 6}" y="12" width="{_PLATE_W - 12}" height="30">
            <div xmlns="http://www.w3.org/1999/xhtml" class="pt-caption">
              <div class="pt-name">{_e(name)}</div>
              <div class="pt-env">{_e(env)}</div>
            </div>
          </foreignObject>
          {_pin_stack(pins.get(node['id'], []))}
        """
        tag = "a" if href else "g"
        href_attr = f' href="{_e(href)}"' if href else ""
        extra = "" if href else " muted"
        devices.append(
            f'<{tag} class="pt-node{on}{extra}"{href_attr} transform="translate({node["x"]},{node["y"]})">{inner}</{tag}>'
        )

    def key(dx: float, letter: str, label: str) -> str:
        return f"""
        <g transform="translate({dx},0)">
          <circle class="legend-pin" r="8" cx="8" cy="0"/>
          <text class="legend-letter" x="8" y="3.2" text-anchor="middle">{letter}</text>
          <text x="22" y="3.4">{label}</text>
        </g>"""

    legend = f"""
    <g class="pt-legend" transform="translate(36,678)">
      <text class="pt-zone-label" x="0" y="0">Agents on a device</text>
      <g transform="translate(0,22)">
        {key(0, 'P', 'Proposer')}
        {key(118, 'O', 'Owner resolver')}
        {key(278, 'A', 'Auditor')}
        {key(396, 'E', 'Policy engine')}
      </g>
    </g>
    """

    return f"""
    <div class="pt-wrap">
      <svg class="pt-canvas" viewBox="0 0 1240 760" role="img" aria-label="Infrastructure topology">
        <rect width="1240" height="760" fill="#f7f6f2"/>
        {''.join(zones)}
        {''.join(links)}
        {''.join(devices)}
        {legend}
      </svg>
    </div>
    """
