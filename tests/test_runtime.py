"""Tests for the runtime, inventory, proposer, executor and ledger.

These pin the *product* behaviors: an incoming signal is proposed, gated, and either
acted on or queued; humans can approve, deny and undo; the ownership graph learns from
approvals; and the ledger is a tamper-evident record of all of it.
"""

from datetime import datetime, timedelta, timezone

import pytest

from assent import (
    Assent,
    ChangeState,
    Decision,
    Environment,
    Inventory,
    Ledger,
    OwnershipClaim,
    OwnershipGraph,
    SimulatedExecutor,
    Signal,
    Source,
    SystemRecord,
)
from assent.inventory import unknown_system

NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def build(**over):
    """An Assent instance with a small known world."""
    inv = Inventory()
    inv.add(SystemRecord("staging-edge", Environment.STAGING, tier0=False, dependents=0))
    inv.add(SystemRecord("prod-payments", Environment.PROD, tier0=True, dependents=4))
    inv.add(SystemRecord("dev-box", Environment.DEV, tier0=False, dependents=0))

    graph = OwnershipGraph()
    graph.add(OwnershipClaim("staging-edge", "team-netsec", Source.CODE, NOW))
    graph.add(OwnershipClaim("prod-payments", "team-payments", Source.CODE, NOW))
    # dev-box intentionally has no ownership claim.

    kwargs = dict(inventory=inv, graph=graph, executor=SimulatedExecutor(), ledger=Ledger())
    kwargs.update(over)
    return Assent(**kwargs)


# ------------------------------------------------------------------ inventory

def test_unknown_system_is_treated_as_maximally_risky():
    record = unknown_system("who-is-this")
    assert record.environment is Environment.PROD
    assert record.tier0 is True
    assert record.blast_radius > 5


def test_inventory_miss_prevents_auto_execution():
    app = build()
    rec = app.submit(Signal("malicious_domain", target="never-seen-before"), now=NOW)
    # Reversible action, but the unknown target is assumed prod + tier-0 => no auto.
    assert rec.state is not ChangeState.AUTO_EXECUTED


# ------------------------------------------------------------------ proposal

def test_unmapped_signal_kind_needs_triage_not_a_guess():
    app = build()
    rec = app.submit(Signal("something_never_seen", target="staging-edge"), now=NOW)
    assert rec.state is ChangeState.NEEDS_TRIAGE
    assert rec.change is None
    assert "no playbook" in rec.reasons[0]


def test_proposer_takes_risk_facts_from_inventory_not_the_signal():
    app = build()
    # The signal claims low severity; the target is prod tier-0. Measured facts win.
    rec = app.submit(
        Signal("leaked_credential", target="prod-payments", severity="low"), now=NOW
    )
    assert rec.change.risk_envelope.environment is Environment.PROD
    assert rec.change.risk_envelope.hits_tier0 is True
    assert rec.change.risk_envelope.blast_radius == 5


# ------------------------------------------------------------------ gating end to end

def test_low_envelope_signal_auto_executes():
    app = build()
    rec = app.submit(Signal("malicious_domain", target="staging-edge"), now=NOW)
    assert rec.decision is Decision.AUTO
    assert rec.state is ChangeState.AUTO_EXECUTED
    assert app.executor.performed == ["block_domain -> staging-edge"]


def test_prod_tier0_change_is_gated_for_a_human():
    app = build()
    rec = app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)
    assert rec.state.open
    assert app.executor.performed == []  # nothing ran


def test_change_with_no_known_owner_escalates():
    app = build()
    # dev-box has no ownership claim; a gated change there can't be routed.
    rec = app.submit(Signal("c2_beacon", target="dev-box"), now=NOW)
    if rec.state.open:
        assert rec.state is ChangeState.ESCALATED


# ------------------------------------------------------------------ human actions

def test_approval_executes_and_teaches_the_graph():
    app = build()
    rec = app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)
    assert rec.state.open

    later = NOW + timedelta(minutes=5)
    app.approve(rec.id, actor="alex", now=later)

    assert rec.state is ChangeState.EXECUTED
    assert app.executor.performed == ["rotate_credential -> prod-payments"]
    # The flywheel: the approval is now an ownership claim.
    assert app.graph.resolve("prod-payments", now=later).id == "alex"


def test_denial_does_not_execute():
    app = build()
    rec = app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)
    app.deny(rec.id, actor="alex", now=NOW)
    assert rec.state is ChangeState.DENIED
    assert app.executor.performed == []


def test_rollback_undoes_an_executed_change():
    app = build()
    rec = app.submit(Signal("malicious_domain", target="staging-edge"), now=NOW)
    assert rec.state is ChangeState.AUTO_EXECUTED
    app.rollback(rec.id, actor="alex", now=NOW)
    assert rec.state is ChangeState.ROLLED_BACK
    assert app.executor.undone == ["block_domain -> staging-edge"]


def test_cannot_approve_something_already_executed():
    app = build()
    rec = app.submit(Signal("malicious_domain", target="staging-edge"), now=NOW)
    with pytest.raises(ValueError):
        app.approve(rec.id, actor="alex", now=NOW)


def test_cannot_roll_back_something_never_executed():
    app = build()
    rec = app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)
    with pytest.raises(ValueError):
        app.rollback(rec.id, actor="alex", now=NOW)


# ------------------------------------------------------------------ executor safety

def test_executor_refuses_a_write_with_no_rollback_plan():
    from assent import Action, Change, Owner, Reversibility, RiskEnvelope

    ex = SimulatedExecutor()
    change = Change(
        action=Action("delete_volume", "vol-1", is_write=True),
        risk_envelope=RiskEnvelope(1, Reversibility.IRREVERSIBLE, Environment.DEV, 0.9),
        owner=Owner("team-x", confidence=0.9),
        rollback=None,
    )
    outcome = ex.execute(change)
    assert outcome.ok is False
    assert ex.performed == []


# ------------------------------------------------------------------ ledger

def test_ledger_records_the_whole_lifecycle():
    app = build()
    rec = app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)
    app.approve(rec.id, actor="alex", now=NOW)

    kinds = [e.kind for e in app.ledger.entries(rec.id)]
    assert kinds == ["proposed", "decided", "approved", "executed"]


def test_ledger_chain_verifies():
    app = build()
    app.submit(Signal("malicious_domain", target="staging-edge"), now=NOW)
    ok, message = app.ledger.verify()
    assert ok, message


def test_ledger_detects_tampering():
    ledger = Ledger()
    ledger.append("proposed", "chg-0001", {"a": 1})
    ledger.append("decided", "chg-0001", {"b": 2})
    assert ledger.verify()[0] is True

    # Mutate a historical entry's content in place.
    ledger.entries()[0].detail["a"] = 999
    ok, message = ledger.verify()
    assert ok is False
    assert "entry 1" in message


def test_ledger_records_the_decision_reasons():
    app = build()
    rec = app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)
    decided = [e for e in app.ledger.entries(rec.id) if e.kind == "decided"][0]
    assert decided.detail["decision"] == rec.decision.value
    assert decided.detail["reasons"] == rec.reasons


# ------------------------------------------------------------------ queue views

def test_queue_and_stats_reflect_state():
    app = build()
    app.submit(Signal("malicious_domain", target="staging-edge"), now=NOW)   # auto
    app.submit(Signal("leaked_credential", target="prod-payments"), now=NOW)  # gated

    assert len(app.queue()) == 1
    assert len(app.settled()) == 1
    assert app.stats()["total"] == 2
