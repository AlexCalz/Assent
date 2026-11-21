"""Tests for the independent audit agent and its deterministic escalation.

Pins the safety property from ``docs/objectives.md`` / ``docs/policy-engine.md``: the
auditor forms its *own* read of the risk, and acting-vs-audit disagreement is itself a
deterministic escalation. The audit signal can only ever tighten the gate.
"""

import pytest

from assent import (
    Action,
    AuditOpinion,
    Change,
    Decision,
    Environment,
    Owner,
    PolicyEngine,
    Reversibility,
    RiskEnvelope,
    RuleBasedAuditor,
)


OWNER = Owner("team-x", source="code", confidence=0.9)


def make_change(
    *,
    action_type="block_domain",
    is_write=True,
    blast_radius=1,
    reversibility=Reversibility.REVERSIBLE,
    environment=Environment.STAGING,
    confidence=0.95,
    hits_tier0=False,
    rollback="undo it",
    context_caution=False,
):
    return Change(
        action=Action(action_type, target="sys-1", is_write=is_write),
        risk_envelope=RiskEnvelope(
            blast_radius=blast_radius,
            reversibility=reversibility,
            environment=environment,
            confidence=confidence,
            hits_tier0=hits_tier0,
        ),
        owner=OWNER,
        rollback=rollback,
        context_caution=context_caution,
    )


@pytest.fixture
def engine():
    return PolicyEngine()


@pytest.fixture
def auditor():
    return RuleBasedAuditor()


# --- The auditor forms an independent read from measured facts ---

def test_auditor_penalizes_prod_and_irreversibility(auditor):
    safe = auditor.review(make_change())
    prod = auditor.review(make_change(environment=Environment.PROD))
    irreversible = auditor.review(
        make_change(reversibility=Reversibility.IRREVERSIBLE)
    )
    assert prod.confidence < safe.confidence
    assert irreversible.confidence < safe.confidence


def test_auditor_ignores_the_acting_confidence(auditor):
    # Two changes identical except the acting agent's (poisonable) confidence number.
    low = auditor.review(make_change(confidence=0.01))
    high = auditor.review(make_change(confidence=0.99))
    # The auditor's independent read must not move with the acting number.
    assert low.confidence == high.confidence


def test_auditor_dissents_on_uncatalogued_action(auditor):
    opinion = auditor.review(make_change(action_type="frobnicate"))
    assert opinion.dissent is True


def test_auditor_dissents_when_confidence_collapses(auditor):
    # prod + tier0 + irreversible + no rollback should collapse below the dissent floor.
    opinion = auditor.review(
        make_change(
            environment=Environment.PROD,
            hits_tier0=True,
            reversibility=Reversibility.IRREVERSIBLE,
            rollback=None,
        )
    )
    assert opinion.dissent is True


# --- Disagreement is itself an escalation trigger (deterministic) ---

def test_divergence_escalates(engine):
    change = make_change(confidence=0.98)  # acting is very sure
    skeptical = AuditOpinion(confidence=0.40, rationale="I'm not convinced")
    result = engine.evaluate(change, audit=skeptical)
    assert result.decision is Decision.ESCALATE
    assert any("diverge" in r for r in result.reasons)


def test_dissent_escalates_even_when_envelope_is_low(engine):
    change = make_change()  # otherwise a clean AUTO
    result = engine.evaluate(change, audit=AuditOpinion(0.9, "object", dissent=True))
    assert result.decision is Decision.ESCALATE


# --- The audit read only tightens: agreement leaves the decision intact ---

def test_agreeing_auditor_leaves_auto_intact(engine, auditor):
    change = make_change()
    result = engine.evaluate(change, audit=auditor.review(change))
    assert result.decision is Decision.AUTO


def test_audit_cannot_open_a_gate_the_envelope_closed(engine):
    # Prod write is gated by measured facts; a maximally confident auditor can't open it.
    change = make_change(environment=Environment.PROD)
    result = engine.evaluate(change, audit=AuditOpinion(1.0, "looks fine to me"))
    assert result.decision is not Decision.AUTO


def test_low_but_close_audit_confidence_tightens_auto_to_gate(engine):
    # Divergence within threshold (no escalate), but the more-conservative audit number
    # sits below the auto floor -> the effective confidence tightens AUTO to a human.
    change = make_change(confidence=0.90)
    cautious = AuditOpinion(confidence=0.70, rationale="borderline")  # gap 0.20 < 0.25
    result = engine.evaluate(change, audit=cautious)
    assert result.decision is not Decision.AUTO
    assert any("audit read" in r for r in result.reasons)


# --- Backward compatibility: no audit opinion == prior behavior ---

def test_no_audit_opinion_preserves_auto(engine):
    assert engine.evaluate(make_change()).decision is Decision.AUTO


def test_invalid_audit_confidence_rejected():
    with pytest.raises(ValueError):
        AuditOpinion(confidence=1.4)
