"""Packet Tracer-style infrastructure canvas.

Not a card grid: zones, labeled devices, links, and live agent pins on the
nodes where work is happening — the Cisco Packet Tracer overview, remapped
onto Assent's inventory + open changes.
"""

from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence, Tuple

from assent.agents import AgentView
from assent.inventory import Inventory
from assent.runtime import Assent, ChangeRecord

_e = html.escape


# Fabric nodes that exist so the diagram reads as a network, not a CMDB dump.
# Inventory systems are overlaid onto these coordinates when present.
_FABRIC: Tuple[dict, ...] = (
    {"id": "internet", "label": "Internet", "kind": "cloud", "x": 560, "y": 58, "zone": "wan"},
    {"id": "staging-edge-fw", "label": "Edge FW", "kind": "firewall", "x": 560, "y": 168, "zone": "edge"},
    {"id": "stg-access-sw", "label": "Stg Access", "kind": "switch", "x": 220, "y": 300, "zone": "staging"},
    {"id": "laptop-4471", "label": "laptop-4471", "kind": "endpoint", "x": 220, "y": 430, "zone": "staging"},
    {"id": "prod-core-sw", "label": "Prod Core", "kind": "switch", "x": 560, "y": 300, "zone": "prod"},
    {"id": "auth-service", "label": "auth-service", "kind": "identity", "x": 430, "y": 430, "zone": "prod"},
    {"id": "payments-api", "label": "payments-api", "kind": "server", "x": 560, "y": 430, "zone": "prod"},
    {"id": "analytics-worker", "label": "analytics-worker", "kind": "server", "x": 690, "y": 430, "zone": "prod"},
    {"id": "payments-latency", "label": "payments-latency", "kind": "server", "x": 560, "y": 540, "zone": "prod"},
    {"id": "dev-sandbox-07", "label": "dev-sandbox-07", "kind": "server", "x": 900, "y": 360, "zone": "dev"},
)

_LINKS: Tuple[Tuple[str, str], ...] = (
    ("internet", "staging-edge-fw"),
    ("staging-edge-fw", "stg-access-sw"),
    ("stg-access-sw", "laptop-4471"),
    ("staging-edge-fw", "prod-core-sw"),
    ("staging-edge-fw", "dev-sandbox-07"),
    ("prod-core-sw", "auth-service"),
    ("prod-core-sw", "payments-api"),
    ("prod-core-sw", "analytics-worker"),
    ("payments-api", "payments-latency"),
)

_ZONES: Tuple[dict, ...] = (
    {"id": "wan", "label": "WAN", "x": 470, "y": 12, "w": 180, "h": 92, "fill": "#e8eef2"},
    {"id": "edge", "label": "Edge / DMZ", "x": 470, "y": 118, "w": 180, "h": 100, "fill": "#f3ead6"},
    {"id": "staging", "label": "Staging", "x": 120, "y": 240, "w": 200, "h": 260, "fill": "#e7f1ea"},
    {"id": "prod", "label": "Production", "x": 370, "y": 240, "w": 400, "h": 370, "fill": "#f6e7e7"},
    {"id": "dev", "label": "Dev", "x": 810, "y": 240, "w": 180, "h": 220, "fill": "#e7eef6"},
)

_KIND_MARK = {
    "cloud": "☁",
    "firewall": "FW",
    "switch": "SW",
    "server": "SRV",
    "endpoint": "PC",
    "identity": "ID",
}


def _index() -> Dict[str, dict]:
    return {n["id"]: n for n in _FABRIC}


def pins_for(app: Assent, agents: Sequence[AgentView]) -> Dict[str, List[dict]]:
    """Map inventory system → agents currently touching it."""
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

    # Always mark systems that have open work even if roster is idle.
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


def _icon(kind: str, x: float, y: float, hot: bool) -> str:
    stroke = "#0f5c57" if hot else "#2c3a44"
    fill = "#f4fffc" if hot else "#fbfbf8"
    if kind == "cloud":
        return f"""
        <g transform="translate({x},{y})">
          <ellipse cx="0" cy="4" rx="34" ry="16" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
          <ellipse cx="-18" cy="-2" rx="14" ry="12" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
          <ellipse cx="16" cy="-4" rx="16" ry="13" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
        </g>"""
    if kind == "firewall":
        return f"""
        <g transform="translate({x},{y})">
          <rect x="-28" y="-18" width="56" height="36" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
          <path d="M-20 -6 H20 M-20 0 H20 M-20 6 H20" stroke="{stroke}" stroke-width="1.4"/>
          <rect x="-28" y="-18" width="8" height="36" fill="{stroke}" opacity="0.18"/>
          <rect x="20" y="-18" width="8" height="36" fill="{stroke}" opacity="0.18"/>
        </g>"""
    if kind == "switch":
        return f"""
        <g transform="translate({x},{y})">
          <rect x="-32" y="-12" width="64" height="24" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
          <g fill="{stroke}">
            <rect x="-24" y="-4" width="8" height="8" rx="1"/>
            <rect x="-10" y="-4" width="8" height="8" rx="1"/>
            <rect x="4" y="-4" width="8" height="8" rx="1"/>
            <rect x="18" y="-4" width="8" height="8" rx="1"/>
          </g>
        </g>"""
    if kind == "endpoint":
        return f"""
        <g transform="translate({x},{y})">
          <rect x="-26" y="-18" width="52" height="32" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
          <rect x="-20" y="-12" width="40" height="20" fill="#152028"/>
          <rect x="-10" y="14" width="20" height="4" fill="{stroke}"/>
          <rect x="-16" y="18" width="32" height="3" rx="1" fill="{stroke}"/>
        </g>"""
    if kind == "identity":
        return f"""
        <g transform="translate({x},{y})">
          <rect x="-22" y="-22" width="44" height="44" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
          <circle cx="0" cy="-6" r="8" fill="none" stroke="{stroke}" stroke-width="1.6"/>
          <path d="M-14 16 q14 -16 28 0" fill="none" stroke="{stroke}" stroke-width="1.6"/>
        </g>"""
    # server
    return f"""
    <g transform="translate({x},{y})">
      <rect x="-18" y="-24" width="36" height="48" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>
      <rect x="-12" y="-16" width="24" height="6" rx="1" fill="{stroke}" opacity="0.18"/>
      <rect x="-12" y="-6" width="24" height="6" rx="1" fill="{stroke}" opacity="0.18"/>
      <rect x="-12" y="4" width="24" height="6" rx="1" fill="{stroke}" opacity="0.18"/>
      <circle cx="0" cy="18" r="2.4" fill="{stroke}"/>
    </g>"""


def _pin_stack(x: float, y: float, pins: List[dict]) -> str:
    bits = []
    for i, pin in enumerate(pins[:4]):
        dx = -18 + i * 16
        letter = {"proposer": "P", "ownership": "O", "auditor": "A", "policy": "E"}.get(
            pin["role"], "?"
        )
        title = _e(f"{pin['name']} — {pin['note']}")
        bits.append(
            f"""<g transform="translate({x + dx},{y - 40})" class="agent-pin pin-{_e(pin['status'])}">
              <title>{title}</title>
              <circle r="9" />
              <text text-anchor="middle" dy="3.5">{letter}</text>
            </g>"""
        )
    return "".join(bits)


def render_topology(
    app: Assent,
    agents: Sequence[AgentView],
    *,
    selected: Optional[str] = None,
) -> str:
    """SVG canvas. ``selected`` is an inventory system name to highlight."""
    nodes = _index()
    inventory: Inventory = app.inventory
    pins = pins_for(app, agents)
    open_targets = {r.signal.target for r in app.queue()}
    href_for: Dict[str, str] = {}
    for record in app.queue():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")
    for record in app.records():
        href_for.setdefault(record.signal.target, f"/change/{record.id}")

    zones = []
    for z in _ZONES:
        zones.append(
            f"""<g class="pt-zone zone-{z['id']}">
              <rect x="{z['x']}" y="{z['y']}" width="{z['w']}" height="{z['h']}" rx="16"
                    fill="{z['fill']}" stroke="rgba(21,32,40,0.10)"/>
              <text x="{z['x'] + 14}" y="{z['y'] + 22}" class="pt-zone-label">{_e(z['label'])}</text>
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
        sys = inventory.lookup(node["id"])
        known = sys is not None
        hot = node["id"] in open_targets or node["id"] == selected
        href = href_for.get(node["id"], "")
        meta = ""
        if sys is not None:
            meta = f"{sys.environment.value}" + (" · tier-0" if sys.tier0 else "")
        elif node["kind"] in {"cloud", "switch"}:
            meta = "fabric"
        label = sys.name if sys is not None else node["label"]
        on = " on" if node["id"] == selected else ""
        inner = f"""
            {_icon(node['kind'], 0, 0, hot)}
            <text class="pt-label" y="42" text-anchor="middle">{_e(label)}</text>
            <text class="pt-meta" y="56" text-anchor="middle">{_e(meta or _KIND_MARK.get(node['kind'], ''))}</text>
            {_pin_stack(0, 0, pins.get(node['id'], []))}
        """
        if href:
            devices.append(
                f'<a class="pt-node{on}" href="{_e(href)}" transform="translate({node["x"]},{node["y"]})">{inner}</a>'
            )
        else:
            devices.append(
                f'<g class="pt-node{on} muted" transform="translate({node["x"]},{node["y"]})">{inner}</g>'
            )
        _ = known  # inventory miss is still drawn as fabric

    legend = """
    <g class="pt-legend" transform="translate(24,600)">
      <text class="pt-zone-label" x="0" y="0">Agents on a node</text>
      <g transform="translate(0,18)">
        <circle class="agent-pin pin-working" r="8" cx="8" cy="0"/><text x="22" y="4">P proposer</text>
        <circle class="agent-pin pin-working" r="8" cx="128" cy="0"/><text x="142" y="4">O owner resolver</text>
        <circle class="agent-pin pin-blocked" r="8" cx="292" cy="0"/><text x="306" y="4">A auditor</text>
        <circle class="agent-pin pin-complete" r="8" cx="412" cy="0"/><text x="426" y="4">E policy engine</text>
      </g>
    </g>
    """

    return f"""
    <div class="pt-wrap">
      <svg class="pt-canvas" viewBox="0 0 1100 640" role="img" aria-label="Infrastructure topology">
        <defs>
          <pattern id="pt-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(21,32,40,0.05)" stroke-width="1"/>
          </pattern>
        </defs>
        <rect width="1100" height="640" fill="#f3f1ea"/>
        <rect width="1100" height="640" fill="url(#pt-grid)"/>
        {''.join(zones)}
        {''.join(links)}
        {''.join(devices)}
        {legend}
      </svg>
    </div>
    """
