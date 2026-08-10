"""Tests for the ownership graph resolver.

Each test pins a claim from ``docs/graph-strategy.md``: derive don't demand, a
cheapest-to-richest ladder, confidence-scored edges with corroboration up and staleness
down, human confirmation as the flywheel, and — the safety property — an incomplete
graph degrading to an unknown owner so the engine escalates.
"""

from datetime import datetime, timedelta, timezone

import pytest

from assent.change import Environment, Reversibility, RiskEnvelope, Action, Change
from assent.graph import OwnershipClaim, OwnershipGraph, Source
from assent.policy import Decision, PolicyEngine


NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def fresh(system, owner, source, days_ago=0, strength=None):
    return OwnershipClaim(
        system=system,
        owner_id=owner,
        source=source,
        observed_at=NOW - timedelta(days=days_ago),
        strength=strength,
    )


# --- Safety property: unknown system degrades to an unknown owner ---

def test_unknown_system_resolves_to_unknown_owner():
    owner = OwnershipGraph().resolve("svc-nobody-knows", now=NOW)
    assert not owner.known
    assert owner.confidence == 0.0


# --- The ladder: a stronger source wins over a weaker one for the same system ---

def test_code_source_outranks_docs_for_conflicting_owner():
    g = OwnershipGraph()
    g.add(fresh("svc-a", "team-code", Source.CODE))
    g.add(fresh("svc-a", "team-docs", Source.DOCS))
    owner = g.resolve("svc-a", now=NOW)
    assert owner.id == "team-code"


# --- Confidence-scored edges: corroboration raises confidence above either alone ---

def test_corroboration_raises_confidence():
    g_single = OwnershipGraph().add(fresh("svc-b", "team-x", Source.OPS))
    single = g_single.resolve("svc-b", now=NOW).confidence

    g_double = OwnershipGraph()
    g_double.add(fresh("svc-b", "team-x", Source.OPS))
    g_double.add(fresh("svc-b", "team-x", Source.CLOUD))
    corroborated = g_double.resolve("svc-b", now=NOW).confidence

    assert corroborated > single


def test_corroboration_notes_provenance_count():
    g = OwnershipGraph()
    g.add(fresh("svc-b", "team-x", Source.CODE))
    g.add(fresh("svc-b", "team-x", Source.OPS))
    owner = g.resolve("svc-b", now=NOW)
    # Strongest source named first, plus a count of the corroborating claims.
    assert owner.source.startswith("code")
    assert "+1" in owner.source


# --- Staleness decays confidence; a very old claim erodes toward nothing ---

def test_staleness_decays_confidence():
    recent = OwnershipGraph().add(fresh("svc-c", "team-y", Source.OPS, days_ago=0))
    stale = OwnershipGraph().add(fresh("svc-c", "team-y", Source.OPS, days_ago=90))
    assert stale.resolve("svc-c", now=NOW).confidence < recent.resolve("svc-c", now=NOW).confidence


def test_ancient_claim_decays_below_a_fresh_weaker_source():
    # A very old high-tier claim can lose to a fresh lower-tier one — freshness matters.
    g = OwnershipGraph()
    g.add(fresh("svc-d", "team-old", Source.CODE, days_ago=3650))   # ~10 years, decayed to ~nothing
    g.add(fresh("svc-d", "team-new", Source.CLOUD, days_ago=0))
    assert g.resolve("svc-d", now=NOW).id == "team-new"


# --- The flywheel: a human confirmation is the strongest signal and refreshes ownership ---

def test_human_confirmation_overrides_stale_machine_claim():
    g = OwnershipGraph()
    g.add(fresh("svc-e", "team-stale", Source.CODE, days_ago=400))
    g.record_human_confirmation("svc-e", "team-real", now=NOW)
    owner = g.resolve("svc-e", now=NOW)
    assert owner.id == "team-real"
    assert owner.confidence > 0.9


# --- End-to-end: resolver output feeds the policy engine's gate ---

def test_resolved_owner_routes_when_confident_else_escalates():
    engine = PolicyEngine()
    g = OwnershipGraph()
    g.add(fresh("prod-db", "team-data", Source.CODE))  # confident, fresh

    def prod_write(owner):
        return Change(
            action=Action("rotate_credential", target="prod-db", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1,
                reversibility=Reversibility.RECOVERABLE,
                environment=Environment.PROD,
                confidence=0.9,
            ),
            owner=owner,
            rollback="re-issue prior credential",
        )

    confident = engine.evaluate(prod_write(g.resolve("prod-db", now=NOW)))
    assert confident.decision is Decision.ROUTE_TO_OWNER

    # A system the graph has never seen -> unknown owner -> escalate, not guess.
    unknown = engine.evaluate(prod_write(g.resolve("prod-mystery", now=NOW)))
    assert unknown.decision is Decision.ESCALATE


def test_weak_claim_strength_override_lowers_confidence():
    # A wildcard CODEOWNERS match is weaker than an exact one; strength models that.
    exact = OwnershipGraph().add(fresh("svc-f", "team-z", Source.CODE))
    wildcard = OwnershipGraph().add(fresh("svc-f", "team-z", Source.CODE, strength=0.3))
    assert wildcard.resolve("svc-f", now=NOW).confidence < exact.resolve("svc-f", now=NOW).confidence
