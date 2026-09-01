"""Invariant tests for the deterministic policy engine.

Each test names the principle from ``docs/objectives.md`` / ``docs/policy-engine.md``
it pins down. If one of these ever fails, the trust story is broken — that is the
point of making the decision "code: auditable, testable, versioned."
"""

import pytest

from assent import (
    Action,
    Change,
    Decision,
    Environment,
    Owner,
    PolicyEngine,
    Reversibility,
    RiskEnvelope,
)
from assent.policy import AutonomyPolicy


CONFIDENT_OWNER = Owner(id="team-payments", source="codeowners", confidence=0.95)
UNKNOWN_OWNER = Owner(id="unknown", source="unknown", confidence=0.0)


def make_change(
    *,
    action_type="block_domain",
    is_write=True,
    target="evil.example.com",
    blast_radius=1,
    reversibility=Reversibility.REVERSIBLE,
    environment=Environment.STAGING,
    confidence=0.95,
    hits_tier0=False,
    owner=CONFIDENT_OWNER,
    rollback="remove domain from blocklist",
    context_caution=False,
):
    return Change(
        action=Action(type=action_type, target=target, is_write=is_write),
        risk_envelope=RiskEnvelope(
            blast_radius=blast_radius,
            reversibility=reversibility,
            environment=environment,
            confidence=confidence,
            hits_tier0=hits_tier0,
        ),
        owner=owner,
        rollback=rollback,
        context_caution=context_caution,
    )


@pytest.fixture
def engine():
    return PolicyEngine()


# --- The happy path: a genuinely low-envelope write earns AUTO ---

def test_low_envelope_reversible_staging_write_auto_executes(engine):
    result = engine.evaluate(make_change())
    assert result.decision is Decision.AUTO


# --- Reads are autonomous (real trust boundary is read vs write) ---

def test_reads_are_autonomous(engine):
    result = engine.evaluate(
        make_change(action_type="read_posture", is_write=False, rollback=None)
    )
    assert result.decision is Decision.AUTO


# --- The catalog is the safety boundary: unknown action fails safe to human ---

def test_uncatalogued_action_escalates(engine):
    result = engine.evaluate(make_change(action_type="frobnicate_the_reactor"))
    assert result.decision is Decision.ESCALATE
    assert any("catalog" in r for r in result.reasons)


# --- No rollback => no autonomy, ever ---

def test_write_without_rollback_never_auto(engine):
    result = engine.evaluate(make_change(rollback=None))
    assert result.decision is not Decision.AUTO


# --- Gate on risk-to-act: prod is out of the auto set even at high confidence ---

def test_prod_write_gates_even_at_max_confidence(engine):
    result = engine.evaluate(make_change(environment=Environment.PROD, confidence=1.0))
    assert result.decision is not Decision.AUTO


# --- Irreversible actions never auto-execute ---

def test_irreversible_action_never_auto(engine):
    result = engine.evaluate(
        make_change(
            action_type="delete_volume",
            reversibility=Reversibility.IRREVERSIBLE,
            rollback=None,  # irreversible has no real undo
        )
    )
    assert result.decision is not Decision.AUTO


def test_catalog_reversibility_ceiling_beats_optimistic_envelope(engine):
    # Envelope claims REVERSIBLE, but the catalog says delete_volume is IRREVERSIBLE.
    # The more conservative classification must win.
    result = engine.evaluate(
        make_change(
            action_type="delete_volume",
            reversibility=Reversibility.REVERSIBLE,
        )
    )
    assert result.decision is not Decision.AUTO


# --- Blast radius can close the gate ---

def test_wide_blast_radius_gates(engine):
    result = engine.evaluate(make_change(blast_radius=500))
    assert result.decision is not Decision.AUTO


def test_tier0_target_never_auto(engine):
    result = engine.evaluate(make_change(hits_tier0=True))
    assert result.decision is not Decision.AUTO


# --- D6 core: confidence only tightens, never opens ---

def test_low_confidence_forces_human_even_with_low_envelope(engine):
    result = engine.evaluate(make_change(confidence=0.10))
    assert result.decision is not Decision.AUTO
    assert any("confidence" in r for r in result.reasons)


def test_high_confidence_cannot_open_a_measured_closed_gate(engine):
    # Prod + max confidence must still gate. Confidence is not a key to the gate.
    result = engine.evaluate(make_change(environment=Environment.PROD, confidence=1.0))
    assert result.decision is not Decision.AUTO


# --- Context raises caution, never grants permission (poisoned-doc defense) ---

def test_context_caution_can_only_tighten(engine):
    baseline = engine.evaluate(make_change(context_caution=False))
    cautious = engine.evaluate(make_change(context_caution=True))
    assert baseline.decision is Decision.AUTO
    assert cautious.decision.rank >= baseline.decision.rank
    assert cautious.decision is not Decision.AUTO


# --- Ownership routing: confident owner routes, unknown owner escalates ---

def test_gate_with_confident_owner_routes_to_owner(engine):
    # Prod write (gated) with a known owner => route, not escalate.
    result = engine.evaluate(
        make_change(environment=Environment.PROD, owner=CONFIDENT_OWNER)
    )
    assert result.decision is Decision.ROUTE_TO_OWNER


def test_gate_with_unknown_owner_escalates_not_guesses(engine):
    result = engine.evaluate(
        make_change(environment=Environment.PROD, owner=UNKNOWN_OWNER)
    )
    assert result.decision is Decision.ESCALATE


def test_low_confidence_owner_escalates_rather_than_silent_route(engine):
    stale = Owner(id="someone-who-left", source="cmdb", confidence=0.30)
    result = engine.evaluate(make_change(environment=Environment.PROD, owner=stale))
    assert result.decision is Decision.ESCALATE


# --- The dial is earned: disabling write autonomy closes AUTO entirely ---

def test_autonomy_dial_off_disables_auto_writes():
    engine = PolicyEngine(autonomy=AutonomyPolicy(allow_auto_writes=False))
    result = engine.evaluate(make_change())  # otherwise a clean AUTO
    assert result.decision is not Decision.AUTO


# --- Determinism: same input, same output, and no exceptions on the envelope guards ---

def test_evaluation_is_deterministic(engine):
    change = make_change()
    first = engine.evaluate(change)
    second = engine.evaluate(change)
    assert first.decision is second.decision
    assert first.reasons == second.reasons


def test_invalid_confidence_rejected():
    with pytest.raises(ValueError):
        RiskEnvelope(
            blast_radius=1,
            reversibility=Reversibility.REVERSIBLE,
            environment=Environment.DEV,
            confidence=1.5,
        )
