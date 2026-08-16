"""Agent roster — live status of Assent's acting / audit / graph roles.

Borrowed from TRIDENT-AI's agent-status sidebar (parallel specialist agents with
live heartbeats), remapped onto Assent's actual architecture:

* **Acting proposer** — turns detections into typed catalog actions
* **Ownership resolver** — JIT graph lookup for the authoritative owner
* **Independent auditor** — second-opinion confidence; can only tighten
* **Policy engine** — deterministic gate (not an LLM agent; shown for transparency)

Status is derived from the runtime's ledger and open queue, not from fake timers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from assent.runtime import Assent


class AgentRole(str, Enum):
    PROPOSER = "proposer"
    OWNERSHIP = "ownership"
    AUDITOR = "auditor"
    POLICY = "policy"


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    COMPLETE = "complete"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AgentView:
    """One row in the agent-status panel."""

    role: AgentRole
    name: str
    title: str
    status: AgentStatus
    detail: str
    last_activity: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "name": self.name,
            "title": self.title,
            "status": self.status.value,
            "detail": self.detail,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
        }


_ROSTER = (
    (AgentRole.PROPOSER, "Acting Proposer", "Diagnose → typed catalog action"),
    (AgentRole.OWNERSHIP, "Ownership Resolver", "JIT owner from the source ladder"),
    (AgentRole.AUDITOR, "Independent Auditor", "Second opinion; can only tighten"),
    (AgentRole.POLICY, "Policy Engine", "Deterministic gate — LLM stays out"),
)


def roster_for(app: "Assent", now: Optional[datetime] = None) -> List[AgentView]:
    """Derive agent statuses from the live runtime — not a scripted animation."""
    now = now or datetime.now(timezone.utc)
    open_count = len(app.queue())
    stats = app.stats()
    total = stats.get("total", 0)
    auto = stats.get("auto_executed", 0)
    escalated = stats.get("escalated", 0)
    pending = stats.get("pending_approval", 0) + stats.get("escalated", 0)

    last = None
    entries = app.ledger.entries()
    if entries:
        last = entries[-1].at

    views: List[AgentView] = []
    for role, name, title in _ROSTER:
        if total == 0:
            status, detail = AgentStatus.IDLE, "Waiting for the first signal"
        elif role is AgentRole.PROPOSER:
            triage = stats.get("needs_triage", 0)
            if triage and open_count:
                status, detail = (
                    AgentStatus.BLOCKED,
                    f"{triage} signal(s) need a human playbook",
                )
            else:
                status, detail = (
                    AgentStatus.COMPLETE,
                    f"Proposed on {total} signal(s)",
                )
        elif role is AgentRole.OWNERSHIP:
            if pending:
                status, detail = (
                    AgentStatus.WORKING,
                    f"Routing {pending} change(s) to owners",
                )
            else:
                status, detail = AgentStatus.COMPLETE, "Owners resolved for active set"
        elif role is AgentRole.AUDITOR:
            if escalated:
                status, detail = (
                    AgentStatus.WORKING,
                    f"Dissented / diverged on {escalated} — escalated",
                )
            else:
                status, detail = AgentStatus.COMPLETE, "Second opinions recorded"
        else:  # POLICY
            if auto and not pending:
                status, detail = (
                    AgentStatus.COMPLETE,
                    f"Auto-assented {auto}; queue clear",
                )
            elif pending:
                status, detail = (
                    AgentStatus.WORKING,
                    f"{pending} awaiting human assent",
                )
            else:
                status, detail = AgentStatus.COMPLETE, f"Gated {total} change(s)"

        views.append(
            AgentView(
                role=role,
                name=name,
                title=title,
                status=status,
                detail=detail,
                last_activity=last or now,
            )
        )
    return views
