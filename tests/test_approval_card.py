"""Tests for the approval-card renderer.

The card only *displays* the engine's decision, so these tests pin that it reflects
real output faithfully — including escaping LLM-produced reasoning, which is untrusted
text that must never be injected as markup.
"""

from html import escape

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
from assent.approval_card import render_card, render_page


def _change(**over):
    base = dict(
        action=Action("block_domain", target="edge-fw", is_write=True),
        risk_envelope=RiskEnvelope(
            blast_radius=1,
            reversibility=Reversibility.REVERSIBLE,
            environment=Environment.STAGING,
            confidence=0.96,
        ),
        owner=Owner("team-netsec", source="code", confidence=0.9),
        reasoning="benign",
        rollback="undo it",
    )
    base.update(over)
    return Change(**base)


def test_card_shows_the_decision_verdict():
    engine = PolicyEngine()
    change = _change()
    result = engine.evaluate(change)
    assert result.decision is Decision.AUTO
    html = render_card(change, result)
    assert "Auto-executed" in html
    assert "block_domain" in html
    assert "edge-fw" in html


def test_card_renders_every_engine_reason():
    engine = PolicyEngine()
    change = _change(  # prod -> gated -> multiple reasons
        risk_envelope=RiskEnvelope(
            blast_radius=1,
            reversibility=Reversibility.REVERSIBLE,
            environment=Environment.PROD,
            confidence=0.96,
        )
    )
    result = engine.evaluate(change)
    rendered = render_card(change, result)
    for reason in result.reasons:
        # Reasons appear in the audit trail, HTML-escaped (quotes become entities).
        assert escape(reason) in rendered


def test_reasoning_text_is_html_escaped():
    engine = PolicyEngine()
    change = _change(reasoning="<script>alert('xss')</script> & <b>bold</b>")
    result = engine.evaluate(change)
    html = render_card(change, result)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_missing_rollback_is_surfaced_not_blank():
    engine = PolicyEngine()
    change = _change(rollback=None, action=Action("delete_volume", "vol-1", is_write=True),
                     risk_envelope=RiskEnvelope(1, Reversibility.IRREVERSIBLE,
                                                Environment.DEV, 0.9))
    result = engine.evaluate(change)
    html = render_card(change, result)
    assert "no rollback plan" in html


def test_card_renders_audit_second_opinion_when_present():
    from assent import AuditOpinion
    engine = PolicyEngine()
    change = _change()
    result = engine.evaluate(change)
    html = render_card(change, result, audit=AuditOpinion(0.4, "borderline signal"))
    assert "Independent audit" in html
    assert "borderline signal" in html


def test_page_is_self_contained_and_themed():
    engine = PolicyEngine()
    items = [(_change(), engine.evaluate(_change()))]
    page = render_page(items)
    assert page.strip().startswith("<!doctype html>")
    assert "http://" not in page and "https://" not in page  # no external assets
    # Theme-aware: all three token states present.
    assert 'prefers-color-scheme: dark' in page
    assert ':root[data-theme="dark"]' in page
