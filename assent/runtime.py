"""The Assent runtime — the product, wired end to end.

One object owns the whole flow described across the concept docs:

    signal -> propose -> resolve owner -> independent audit -> gate -> act or queue

and then the human side of it: approve, deny, roll back. Every step is written to the
tamper-evident ledger, and every human approval feeds the ownership graph (the
flywheel from ``docs/graph-strategy.md``).

The runtime deliberately holds no trust logic of its own. It sequences the parts and
obeys whatever the deterministic ``PolicyEngine`` returns — the decision stays in one
auditable place.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from assent.audit import AuditAgent, AuditOpinion, RuleBasedAuditor
from assent.catalog import ActionCatalog, DEFAULT_CATALOG
from assent.change import Change
from assent.executor import Executor, SimulatedExecutor
from assent.graph import OwnershipGraph
from assent.inventory import Inventory
from assent.ledger import Ledger
from assent.policy import Decision, PolicyEngine
from assent.proposer import Proposer, RuleBasedProposer, Signal


class ChangeState(str, Enum):
    """Where a change sits in its lifecycle."""

    NEEDS_TRIAGE = "needs_triage"        # no proposal could be made — human starts here
    PENDING_APPROVAL = "pending_approval"  # routed to a known owner
    ESCALATED = "escalated"              # broadened: no confident owner or a fail-safe tripped
    AUTO_EXECUTED = "auto_executed"      # low envelope earned it
    EXECUTED = "executed"                # a human approved, then it ran
    DENIED = "denied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"                    # the enforcement layer refused or errored

    @property
    def open(self) -> bool:
        """Is a human still on the hook for this one?"""
        return self in {
            ChangeState.NEEDS_TRIAGE,
            ChangeState.PENDING_APPROVAL,
            ChangeState.ESCALATED,
        }


@dataclass
class ChangeRecord:
    """A change and everything that has happened to it."""

    id: str
    signal: Signal
    state: ChangeState
    created_at: datetime
    change: Optional[Change] = None
    decision: Optional[Decision] = None
    reasons: List[str] = field(default_factory=list)
    audit: Optional[AuditOpinion] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    execution_handle: str = ""

    @property
    def title(self) -> str:
        if self.change is not None:
            return f"{self.change.action.type} → {self.change.action.target}"
        return f"{self.signal.kind} → {self.signal.target}"


class Assent:
    """The control plane. Construct with the pieces; drive with signals and approvals."""

    def __init__(
        self,
        inventory: Optional[Inventory] = None,
        graph: Optional[OwnershipGraph] = None,
        catalog: ActionCatalog = DEFAULT_CATALOG,
        engine: Optional[PolicyEngine] = None,
        proposer: Optional[Proposer] = None,
        auditor: Optional[AuditAgent] = None,
        executor: Optional[Executor] = None,
        ledger: Optional[Ledger] = None,
    ) -> None:
        self.inventory = inventory if inventory is not None else Inventory()
        self.graph = graph if graph is not None else OwnershipGraph()
        self.catalog = catalog
        self.engine = engine or PolicyEngine(catalog=catalog)
        self.proposer = proposer or RuleBasedProposer(self.inventory, catalog)
        self.auditor = auditor or RuleBasedAuditor(catalog)
        self.executor = executor if executor is not None else SimulatedExecutor()
        self.ledger = ledger if ledger is not None else Ledger()

        self._records: Dict[str, ChangeRecord] = {}
        self._ids = itertools.count(1)

    # ---------------------------------------------------------------- ingest

    def submit(self, signal: Signal, now: Optional[datetime] = None) -> ChangeRecord:
        """Run a detection through the full pipeline."""
        now = now or _utcnow()
        change_id = f"chg-{next(self._ids):04d}"

        proposal = self.proposer.propose(signal)
        self.ledger.append(
            "proposed",
            change_id,
            {
                "signal": signal.kind,
                "target": signal.target,
                "proposed": proposal.proposed,
                "refusal": proposal.refusal,
            },
        )

        # No proposal => nothing to gate. Degrade to a human, never guess an action.
        if not proposal.proposed:
            record = ChangeRecord(
                id=change_id,
                signal=signal,
                state=ChangeState.NEEDS_TRIAGE,
                created_at=now,
                reasons=[proposal.refusal],
            )
            self._records[change_id] = record
            return record

        # Ownership is resolved here, not by the proposer — routing authority is measured.
        change = proposal.change
        owner = self.graph.resolve(signal.target, now=now)
        change = _with_owner(change, owner)

        opinion = self.auditor.review(change)
        result = self.engine.evaluate(change, audit=opinion)

        self.ledger.append(
            "decided",
            change_id,
            {
                "decision": result.decision.value,
                "reasons": list(result.reasons),
                "owner": owner.id,
                "owner_confidence": owner.confidence,
                "audit_confidence": opinion.confidence,
                "audit_dissent": opinion.dissent,
            },
        )

        record = ChangeRecord(
            id=change_id,
            signal=signal,
            state=ChangeState.PENDING_APPROVAL,  # provisional; set precisely below
            created_at=now,
            change=change,
            decision=result.decision,
            reasons=list(result.reasons),
            audit=opinion,
        )

        if result.decision is Decision.AUTO:
            self._execute(record, actor="assent", now=now, auto=True)
        elif result.decision is Decision.ROUTE_TO_OWNER:
            record.state = ChangeState.PENDING_APPROVAL
        else:
            record.state = ChangeState.ESCALATED

        self._records[change_id] = record
        return record

    # ---------------------------------------------------------------- human actions

    def approve(self, change_id: str, actor: str, now: Optional[datetime] = None) -> ChangeRecord:
        """A human grants assent. Executes, and teaches the ownership graph."""
        record = self.require(change_id)
        if record.state not in {ChangeState.PENDING_APPROVAL, ChangeState.ESCALATED}:
            raise ValueError(f"{change_id} is not awaiting approval (state={record.state.value})")

        now = now or _utcnow()
        self.ledger.append("approved", change_id, {"by": actor}, actor=actor, at=now)

        # The flywheel: an approval confirms (or corrects) who owns this system.
        self.graph.record_human_confirmation(record.signal.target, actor, now=now)

        self._execute(record, actor=actor, now=now, auto=False)
        return record

    def deny(self, change_id: str, actor: str, now: Optional[datetime] = None) -> ChangeRecord:
        record = self.require(change_id)
        if record.state not in {
            ChangeState.PENDING_APPROVAL,
            ChangeState.ESCALATED,
            ChangeState.NEEDS_TRIAGE,
        }:
            raise ValueError(f"{change_id} is not awaiting a decision (state={record.state.value})")

        now = now or _utcnow()
        record.state = ChangeState.DENIED
        record.resolved_at = now
        record.resolved_by = actor
        self.ledger.append("denied", change_id, {"by": actor}, actor=actor, at=now)
        return record

    def rollback(self, change_id: str, actor: str, now: Optional[datetime] = None) -> ChangeRecord:
        """Undo an executed change — the "every write has a rollback" promise, honored."""
        record = self.require(change_id)
        if record.state not in {ChangeState.AUTO_EXECUTED, ChangeState.EXECUTED}:
            raise ValueError(f"{change_id} has not been executed (state={record.state.value})")

        now = now or _utcnow()
        outcome = self.executor.rollback(record.change, record.execution_handle)
        if outcome.ok:
            record.state = ChangeState.ROLLED_BACK
        else:
            record.state = ChangeState.FAILED
        record.resolved_at = now
        record.resolved_by = actor
        self.ledger.append(
            "rolled_back" if outcome.ok else "failed",
            change_id,
            {"by": actor, "detail": outcome.detail},
            actor=actor,
            at=now,
        )
        return record

    # ---------------------------------------------------------------- queries

    def require(self, change_id: str) -> ChangeRecord:
        record = self._records.get(change_id)
        if record is None:
            raise KeyError(f"unknown change '{change_id}'")
        return record

    def records(self) -> List[ChangeRecord]:
        return list(self._records.values())

    def queue(self) -> List[ChangeRecord]:
        """Everything still awaiting a human, most recent first."""
        return sorted(
            (r for r in self._records.values() if r.state.open),
            key=lambda r: r.created_at,
            reverse=True,
        )

    def settled(self) -> List[ChangeRecord]:
        return sorted(
            (r for r in self._records.values() if not r.state.open),
            key=lambda r: r.created_at,
            reverse=True,
        )

    def stats(self) -> Dict[str, int]:
        counts = {state.value: 0 for state in ChangeState}
        for record in self._records.values():
            counts[record.state.value] += 1
        counts["total"] = len(self._records)
        return counts

    # ---------------------------------------------------------------- internals

    def _execute(self, record: ChangeRecord, actor: str, now: datetime, auto: bool) -> None:
        outcome = self.executor.execute(record.change)
        if outcome.ok:
            record.state = ChangeState.AUTO_EXECUTED if auto else ChangeState.EXECUTED
            record.execution_handle = outcome.handle
        else:
            record.state = ChangeState.FAILED
        record.resolved_at = now
        record.resolved_by = actor
        self.ledger.append(
            "executed" if outcome.ok else "failed",
            record.id,
            {"auto": auto, "detail": outcome.detail, "by": actor},
            actor=actor,
            at=now,
        )


def _with_owner(change: Change, owner) -> Change:
    """Return the change with its owner resolved (``Change`` is frozen by design)."""
    return Change(
        action=change.action,
        risk_envelope=change.risk_envelope,
        owner=owner,
        reasoning=change.reasoning,
        rollback=change.rollback,
        context_caution=change.context_caution,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
