"""Simulate a realistic ARTEX attack chain and show how Assent defends against it.

Recreates the Storm-0940 / ConnectWise supply chain campaign as reported by
Microsoft (October 2026) and GTIG/Mandiant: a multi-stage agentic attack that
goes from compromised app identity to deep cloud access in under three hours.

Each signal arrives at machine speed. Assent's campaign correlator groups them,
the policy engine gates each one, and the approval queue captures everything
the human SOC analyst needs to decide — with the attack's velocity visible in
the campaign context.
"""

from datetime import datetime, timedelta, timezone

from assent import (
    Assent,
    Inventory,
    OwnershipGraph,
    OwnershipClaim,
    Source,
    SystemRecord,
    Environment,
)
from assent.proposer import Signal

# --- Build the defended environment ---

inventory = Inventory()
# ConnectWise cloud backup integration — the entry point
inventory.add(SystemRecord("connectwise-backup", Environment.PROD, tier0=False, dependents=12))
# Azure AD / Entra ID — identity plane
inventory.add(SystemRecord("azure-ad-tenant", Environment.PROD, tier0=True, dependents=85))
# M365 environment — where the pivot lands
inventory.add(SystemRecord("m365-exchange", Environment.PROD, tier0=False, dependents=45))
# AWS production — exfil target
inventory.add(SystemRecord("aws-prod-account", Environment.PROD, tier0=True, dependents=60))
# Internal staging — lower risk
inventory.add(SystemRecord("staging-k8s", Environment.STAGING, tier0=False, dependents=3))

graph = OwnershipGraph()
now = datetime.now(timezone.utc)
graph.add(OwnershipClaim("connectwise-backup", "sre-team@acme.com", Source.OPS, now))
graph.add(OwnershipClaim("azure-ad-tenant", "identity-eng@acme.com", Source.CLOUD, now))
graph.add(OwnershipClaim("azure-ad-tenant", "ciso@acme.com", Source.HUMAN, now))
graph.add(OwnershipClaim("m365-exchange", "it-ops@acme.com", Source.CLOUD, now))
graph.add(OwnershipClaim("aws-prod-account", "cloud-eng@acme.com", Source.CODE, now))
graph.add(OwnershipClaim("aws-prod-account", "sre-team@acme.com", Source.OPS, now))

runtime = Assent(inventory=inventory, graph=graph)

# --- The ARTEX attack chain (modeled on Storm-0940) ---

print("=" * 78)
print("ARTEX ATTACK CHAIN SIMULATION")
print("Modeled on Storm-0940 / ConnectWise supply chain campaign")
print("=" * 78)
print()

t = now
signals = [
    # Phase 1: Initial access via compromised ConnectWise app identity
    (timedelta(seconds=0), Signal(
        kind="supply_chain_pivot",
        target="connectwise-backup",
        summary="ConnectWise Cloud Backup app identity authenticating to M365 tenants "
                "without interactive user sign-in. App credential was modified outside "
                "normal rotation window.",
        indicators={"app_id": "cw-backup-prod-0x4a", "method": "client_credential_grant"},
        source="azure-ad-logs",
        severity="critical",
    )),

    # Phase 2: Credential spray at machine speed (15 seconds later)
    (timedelta(seconds=15), Signal(
        kind="credential_spray_burst",
        target="azure-ad-tenant",
        summary="2,900 sign-in attempts/minute against Azure AD from compromised app "
                "identity. Pattern consistent with ARTEX agent spray module.",
        indicators={"attempts_per_min": "2900", "source_identity": "cw-backup-prod-0x4a"},
        source="azure-ad-logs",
        severity="critical",
    )),

    # Phase 3: Agentic recon burst (40 seconds in)
    (timedelta(seconds=40), Signal(
        kind="agentic_recon_burst",
        target="azure-ad-tenant",
        summary="110,000+ AD object enumeration in 23 seconds. User-agent matches known "
                "ARTEX probe signature. artex-probe-* temp files written to disk.",
        indicators={"objects_enumerated": "110847", "duration_sec": "23", "user_agent": "ArtexProbe/2.1"},
        source="edr-crowdstrike",
        severity="critical",
    )),

    # Phase 4: Kerberos attack chain (90 seconds in)
    (timedelta(seconds=90), Signal(
        kind="kerberos_attack",
        target="azure-ad-tenant",
        summary="Kerberoasting followed by DCSync attempt. ARTEX agent extracted service "
                "account tickets and attempted domain replication.",
        indicators={"technique": "kerberoast+dcsync", "tickets_extracted": "47"},
        source="edr-crowdstrike",
        severity="critical",
    )),

    # Phase 5: OAuth app self-grants Global Admin (2 minutes in)
    (timedelta(seconds=120), Signal(
        kind="oauth_app_abuse",
        target="m365-exchange",
        summary="ConnectWise application assigned itself Global Administrator role via "
                "Microsoft Graph API. No approval flow triggered.",
        indicators={"role": "GlobalAdministrator", "method": "self-assignment"},
        source="azure-ad-logs",
        severity="critical",
    )),

    # Phase 6: Lateral movement burst (3 minutes in)
    (timedelta(seconds=180), Signal(
        kind="lateral_movement_burst",
        target="aws-prod-account",
        summary="Rapid lateral movement via Pass-the-Hash and WinRM from compromised "
                "identity. 27 events in 23 seconds across 4 systems.",
        indicators={"techniques": "PtH,WinRM,KerberosRelay", "events_per_sec": "1.17"},
        source="edr-crowdstrike",
        severity="critical",
    )),

    # Phase 7: Privilege escalation in cloud (4 minutes in)
    (timedelta(seconds=240), Signal(
        kind="privilege_escalation",
        target="aws-prod-account",
        summary="EC2 instance launched with admin role. 100GB EBS volume created — "
                "consistent with ARTEX exfil-staging module.",
        indicators={"instance_type": "m5.xlarge", "volume_size_gb": "100"},
        source="aws-cloudtrail",
        severity="critical",
    )),

    # Phase 8: Exfiltration staging (5 minutes in)
    (timedelta(seconds=300), Signal(
        kind="exfil_staging",
        target="aws-prod-account",
        summary="Data staged to 100GB volume. Output routed to 491 rotating webhook.site "
                "URLs. Pattern matches ARTEX exfil orchestrator.",
        indicators={"webhook_count": "491", "data_volume_gb": "100"},
        source="network-proxy",
        severity="critical",
    )),
]


for dt, signal in signals:
    t_signal = t + dt
    record = runtime.submit(signal, now=t_signal)

    elapsed = dt.total_seconds()
    print(f"T+{elapsed:>5.0f}s  [{signal.kind}]")
    print(f"         Target: {signal.target}")
    print(f"         Decision: {record.decision.value if record.decision else 'NEEDS_TRIAGE'}")
    print(f"         State: {record.state.value}")
    if record.reasons:
        for r in record.reasons[:2]:
            print(f"         → {r}")
    print()

# --- Summary ---
print("=" * 78)
print("CAMPAIGN SUMMARY")
print("=" * 78)

stats = runtime.stats()
print(f"\nTotal signals processed:  {stats['total']}")
print(f"Auto-executed:           {stats['auto_executed']}")
print(f"Pending approval:        {stats['pending_approval']}")
print(f"Escalated:               {stats['escalated']}")
print(f"Needs triage:            {stats['needs_triage']}")

campaigns = runtime.correlator.active_campaigns(t + timedelta(seconds=300))
for c in campaigns:
    print(f"\nCampaign {c.id}:")
    print(f"  Signals:  {len(c.signals)}")
    print(f"  Targets:  {', '.join(sorted(c.targets))}")
    print(f"  Kinds:    {', '.join(sorted(c.kinds))}")
    duration = (c.last_seen - c.first_seen).total_seconds() if c.first_seen and c.last_seen else 0
    print(f"  Duration: {duration:.0f}s")
    print(f"  Multi-stage: {runtime.correlator.is_multi_stage(c)}")

print("\n" + "=" * 78)
print("APPROVAL QUEUE (what the SOC analyst sees)")
print("=" * 78)
for record in runtime.queue():
    print(f"\n  [{record.id}] {record.title}")
    print(f"    State: {record.state.value}")
    if record.audit:
        print(f"    Audit confidence: {record.audit.confidence:.4f}")
        print(f"    Audit dissent: {record.audit.dissent}")
    if record.reasons:
        print(f"    Gate reason: {record.reasons[0]}")

print("\n" + "=" * 78)
print("LEDGER INTEGRITY")
print("=" * 78)
ok, msg = runtime.ledger.verify()
print(f"  Chain valid: {ok}")
print(f"  Entries: {len(runtime.ledger.entries())}")
print(f"  Detail: {msg}")
