# Ownership & Context Graph — Population Strategy

The graph maps `system -> owner` (for approval routing) and `system -> risk-relevant
facts` (for risk assessment). The hard part isn't the schema — it's populating it
without a six-month integration slog. The answer: **derive, don't demand.**

## Three moves that kill the slog

### 1. Lazy, just-in-time resolution
Don't build the org's graph. Resolve ownership + context for **the one system a change
is about to touch, at propose-time.** A months-long integration becomes a per-change
lookup.

### 2. A source ladder — cheapest to richest
Populate from systems that already encode ownership, in priority order:

| Tier | Source | Why it's cheap / good |
|---|---|---|
| 1 | Code & infra: CODEOWNERS, git blame, Terraform/Pulumi state, K8s labels, Helm | Machine-readable, versioned, zero human effort — **day one** |
| 2 | Ops / on-call: PagerDuty, Opsgenie, service catalogs (Backstage/OpsLevel), Slack channel owners | Live, self-maintaining — ops keeps it current for their own reasons |
| 3 | Cloud & asset: resource tags, CMDB (ServiceNow), EDR inventory | Org already maintains for billing/compliance |
| 4 | Identity / access: IAM policies, group membership | Who *can* write ≈ who owns |
| 5 | Documents: runbooks, wikis, postmortems → LLM extraction to structured claims | Also feeds the **context** graph. This is the "feed it internal docs" fuel |
| 6 | Human confirmation: every approval confirms/corrects an edge | Normal operation maintains the graph |

### 3. Confidence-scored edges with provenance
Every edge = `(owner, source, timestamp, confidence)`. Corroboration across tiers
raises confidence; staleness decays it. Feeds gating directly:
- High-confidence owner → route to them.
- Low-confidence / unknown → escalate or broaden. Never a silent auto-route.

## The flywheel
Normal operation maintains the graph. Every human approval either confirms or corrects
an edge, so the graph gets **best exactly where the product is active.** Ship at 30%
coverage — it just asks more often, and each ask fills in the gap.

## Safety property
An incomplete graph degrades to **"ask a human," never "guess and act."** Coverage
gaps cost latency, not safety.

## Trap to respect
Tier 5 (documents) is **untrusted input** the moment an attacker can write to it. A
poisoned runbook must never *lower* a gate. Docs raise caution, never grant permission.
Ownership data also goes stale — stale approver = dangerous change routed to someone who
left. Sync from source-of-truth systems; fall back to escalation on any routing miss.
