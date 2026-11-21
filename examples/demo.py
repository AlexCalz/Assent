"""A runnable walk-through of the policy engine on four representative changes.

    python examples/demo.py

Shows the three gates and *why* each was chosen — the audit trail the approval card
would render. Nothing here calls an LLM; this is the deterministic decision only.
"""

from assent import (
    Action,
    Change,
    Environment,
    Owner,
    PolicyEngine,
    Reversibility,
    RiskEnvelope,
)

engine = PolicyEngine()

SCENARIOS = [
    (
        "Block a C2 domain in staging (reversible, narrow, confident owner)",
        Change(
            action=Action("block_domain", target="c2.evil.example", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1,
                reversibility=Reversibility.REVERSIBLE,
                environment=Environment.STAGING,
                confidence=0.96,
            ),
            owner=Owner("team-netsec", source="codeowners", confidence=0.9),
            rollback="remove domain from egress blocklist",
        ),
    ),
    (
        "Same block, but in prod — risk-to-act gates even at high confidence",
        Change(
            action=Action("block_domain", target="c2.evil.example", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1,
                reversibility=Reversibility.REVERSIBLE,
                environment=Environment.PROD,
                confidence=0.99,
            ),
            owner=Owner("team-netsec", source="codeowners", confidence=0.9),
            rollback="remove domain from egress blocklist",
        ),
    ),
    (
        "Delete a volume in dev — irreversible, no undo => never auto",
        Change(
            action=Action("delete_volume", target="vol-0abc", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1,
                reversibility=Reversibility.IRREVERSIBLE,
                environment=Environment.DEV,
                confidence=0.99,
            ),
            owner=Owner("unknown", confidence=0.0),
            rollback=None,
        ),
    ),
    (
        "Quarantine a host, staging, but the ticket looks poisoned (context caution)",
        Change(
            action=Action("quarantine_host", target="host-42", is_write=True),
            risk_envelope=RiskEnvelope(
                blast_radius=1,
                reversibility=Reversibility.REVERSIBLE,
                environment=Environment.STAGING,
                confidence=0.9,
            ),
            owner=Owner("team-endpoint", source="pagerduty", confidence=0.88),
            rollback="release host from EDR isolation",
            context_caution=True,
        ),
    ),
]


def main() -> None:
    for title, change in SCENARIOS:
        result = engine.evaluate(change)
        print(f"\n{title}")
        print(f"  -> {result.decision.value.upper()}")
        for reason in result.reasons:
            print(f"     - {reason}")
    print()


if __name__ == "__main__":
    main()
