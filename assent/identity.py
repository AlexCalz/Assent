"""Who is speaking, and what they are.

Two kinds of participant appear in the product, and they must never be
confusable at a glance:

* **Agents** — Assent's own machine roles. They carry the agent mark and a
  capability line, never a job title.
* **People** — humans with an org job title next to their name, because the
  whole thesis is that a *named, authoritative* human assented.

Sensors are a third, thinner case: telemetry sources with no authority at all.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Dict, Optional

_e = html.escape


@dataclass(frozen=True)
class Participant:
    id: str
    name: str
    # Agents: what the agent is allowed to do. People: their org job title.
    subtitle: str
    kind: str  # agent | person | sensor
    short: str = ""

    @property
    def is_agent(self) -> bool:
        return self.kind == "agent"

    @property
    def initials(self) -> str:
        bits = [b for b in self.name.replace("-", " ").split() if b]
        if not bits:
            return "?"
        if len(bits) == 1:
            return bits[0][:2].upper()
        return (bits[0][0] + bits[-1][0]).upper()


# --------------------------------------------------------------------- agents

AGENTS: Dict[str, Participant] = {
    "proposer": Participant(
        "proposer", "Proposer", "Diagnoses signals into catalogued actions", "agent"
    ),
    "ownership": Participant(
        "ownership", "Ownership Resolver", "Resolves the authoritative owner", "agent"
    ),
    "auditor": Participant(
        "auditor", "Independent Auditor", "Second opinion — can only tighten", "agent"
    ),
    "policy": Participant(
        "policy", "Policy Engine", "Deterministic gate — no model in the decision", "agent"
    ),
    "assent": Participant(
        "assent", "Assent", "Control plane summary", "agent"
    ),
}


# --------------------------------------------------------------------- people

PEOPLE: Dict[str, Participant] = {
    "you": Participant(
        "you", "Alex Calzada", "Security Operations Lead", "person", short="You"
    ),
    "jordan": Participant(
        "jordan", "Jordan Hale", "Payments Engineering Lead", "person", short="Jordan"
    ),
    "priya": Participant(
        "priya", "Priya Raman", "Identity Platform Lead", "person", short="Priya"
    ),
    "dana": Participant(
        "dana", "Dana Whitfield", "Data Platform Lead", "person", short="Dana"
    ),
}

# Which team id in the ownership graph each person is authoritative for.
TEAM_OF = {
    "jordan": "team-payments",
    "priya": "team-identity",
    "dana": "team-data",
    "you": "soc",
}

SYSTEMS_OF = {
    "jordan": frozenset({"payments-api", "payments-latency"}),
    "priya": frozenset({"auth-service"}),
    "dana": frozenset({"analytics-worker"}),
    "you": frozenset(),
}


def person(actor: str) -> Participant:
    """A human by id. Unknown ids sit at the You desk under their own name."""
    found = PEOPLE.get(actor)
    if found is not None:
        return found
    return Participant(actor, actor, "Security Operations Lead", "person", short=actor)


def agent(role: str) -> Optional[Participant]:
    return AGENTS.get(role)


def sensor(source: str) -> Participant:
    # No subtitle: the SENSOR tag already says what it is, and a sensor has no authority.
    return Participant(source, source.replace("-", " ").title(), "", "sensor")


def resolver(actor_id: str) -> Participant:
    """Map a ledger actor onto a participant — machine actors become agents."""
    if actor_id in {"assent", "", None}:
        return AGENTS["policy"]
    if actor_id in AGENTS:
        return AGENTS[actor_id]
    return person(actor_id)


# --------------------------------------------------------------------- marks

AGENT_MARK = """
<svg class="mark-glyph" viewBox="0 0 24 24" aria-hidden="true">
  <path d="M12 2.6 20.4 7.4v9.2L12 21.4 3.6 16.6V7.4z" fill="none"
        stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
  <circle cx="12" cy="12" r="3.1" fill="currentColor"/>
</svg>
"""

SENSOR_MARK = """
<svg class="mark-glyph" viewBox="0 0 24 24" aria-hidden="true">
  <path d="M3 14.5c2.4 0 2.4-5 4.8-5s2.4 9 4.8 9 2.4-8 4.8-8 1.8 4 3.6 4"
        fill="none" stroke="currentColor" stroke-width="1.6"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def avatar(p: Participant, *, size: str = "") -> str:
    """The identity chip's visual: agent mark, sensor wave, or human monogram."""
    cls = f"avatar avatar-{p.kind}" + (f" {size}" if size else "")
    if p.is_agent:
        return f'<span class="{cls}" title="Assent agent">{AGENT_MARK}</span>'
    if p.kind == "sensor":
        return f'<span class="{cls}" title="Telemetry source">{SENSOR_MARK}</span>'
    return f'<span class="{cls}">{_e(p.initials)}</span>'


def byline(
    p: Participant,
    *,
    meta: str = "",
    is_self: bool = False,
    compact: bool = False,
) -> str:
    """Name line. Agents get the AGENT tag; people get their org job title.

    ``compact`` drops the subtitle for dense contexts (table cells), where the
    tag alone already distinguishes an agent from a person.
    """
    tag = ""
    if p.is_agent:
        tag = '<span class="tag tag-agent">Agent</span>'
    elif p.kind == "sensor":
        tag = '<span class="tag tag-sensor">Sensor</span>'
    elif is_self:
        tag = '<span class="tag tag-you">You</span>'
    sub = (
        f'<span class="byline-sub">{_e(p.subtitle)}</span>'
        if p.subtitle and not compact
        else ""
    )
    meta_html = f'<span class="byline-meta">{_e(meta)}</span>' if meta else ""
    return f"""
    <span class="byline">
      <span class="byline-name">{_e(p.name)}</span>{tag}{sub}{meta_html}
    </span>"""


def identity(
    p: Participant,
    *,
    meta: str = "",
    is_self: bool = False,
    compact: bool = False,
) -> str:
    """Avatar + byline, aligned on one baseline."""
    size = "sm" if compact else ""
    return (
        f'<span class="identity">{avatar(p, size=size)}'
        f'{byline(p, meta=meta, is_self=is_self, compact=compact)}</span>'
    )
