"""Generate the approval-queue page from real end-to-end output.

    python examples/render_cards.py [output.html]

Full slice: the ownership graph resolves each affected system's owner, the policy
engine gates the change, and the approval card renders the decision + audit trail.
Nothing is hand-authored — the page is a view of live engine output.
"""

import sys
from datetime import datetime, timezone

from assent import (
    Action,
    Change,
    Environment,
    OwnershipClaim,
    OwnershipGraph,
    PolicyEngine,
    Reversibility,
    RiskEnvelope,
    Source,
)
from assent.approval_card import render_page

NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def _graph() -> OwnershipGraph:
    g = OwnershipGraph()
    # Fresh, corroborated ownership for the systems our agents touch.
    g.add(OwnershipClaim("edge-fw", "team-netsec", Source.CODE, NOW))
    g.add(OwnershipClaim("edge-fw", "team-netsec", Source.OPS, NOW))
    g.add(OwnershipClaim("payments-api", "team-payments", Source.CODE, NOW))
    g.add(OwnershipClaim("laptop-4471", "team-endpoint", Source.OPS, NOW))
    # analytics-db intentionally absent -> unresolved owner -> escalate.
    return g


def _changes(g: OwnershipGraph):
    """Four representative proposals, each resolving its owner from the graph."""
    return [
        Change(
            action=Action("block_domain", target="edge-fw", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1, reversibility=Reversibility.REVERSIBLE,
                environment=Environment.STAGING, confidence=0.96,
            ),
            owner=g.resolve("edge-fw", now=NOW),
            reasoning="Domain c2.evil.example matches a known C2 pattern in the active "
            "threat feed and appears in egress logs for one host. Blocking is narrow and "
            "reversible.",
            rollback="Remove c2.evil.example from the egress blocklist.",
        ),
        Change(
            action=Action("rotate_credential", target="payments-api", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=3, reversibility=Reversibility.RECOVERABLE,
                environment=Environment.PROD, confidence=0.91, hits_tier0=True,
            ),
            owner=g.resolve("payments-api", now=NOW),
            reasoning="Leaked API key observed in a public paste. Rotation is the fix, but "
            "the key fans out to three consumers and the target is tier-0.",
            rollback="Re-issue the prior key version from the secrets manager and "
            "re-point consumers.",
        ),
        Change(
            action=Action("quarantine_host", target="laptop-4471", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1, reversibility=Reversibility.REVERSIBLE,
                environment=Environment.STAGING, confidence=0.72,
            ),
            owner=g.resolve("laptop-4471", now=NOW),
            reasoning="Beaconing behavior on laptop-4471, but the signal is weaker than a "
            "confident detection — confidence sits below the auto floor.",
            rollback="Release laptop-4471 from EDR network isolation.",
        ),
        Change(
            action=Action("delete_volume", target="analytics-db", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1, reversibility=Reversibility.IRREVERSIBLE,
                environment=Environment.DEV, confidence=0.99,
            ),
            owner=g.resolve("analytics-db", now=NOW),  # unresolved
            reasoning="A scratch volume flagged as holding exposed data. Deletion is "
            "irreversible and no owner is on file for this system.",
            rollback=None,
        ),
    ]


def main() -> None:
    engine = PolicyEngine()
    g = _graph()
    items = [(c, engine.evaluate(c)) for c in _changes(g)]

    out = sys.argv[1] if len(sys.argv) > 1 else "examples/approval_queue.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(render_page(items))

    for change, result in items:
        print(f"{change.action.type:18} -> {result.decision.value}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
