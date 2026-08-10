# The Approval Card — the Hero Component

When Assent can't auto-execute, it routes a `Change` to a human owner. The **approval
card** is what that human sees. It is the single most-used surface in the product and the
place trust is won or lost, one decision at a time. Objective: make approving (or
rejecting) a high-stakes action **fast, complete, and reversible** — so the owner never
feels they're rubber-stamping and never feels they're guessing.

## The job of the card

One human, one decision, under time pressure, often on a phone. The card must answer four
questions in the order a cautious operator actually asks them:

1. **What will happen?** — exact command + target, in plain terms.
2. **How bad if it's wrong?** — blast radius, environment, reversibility.
3. **Why does the agent think this?** — reasoning grounded in *our* docs, with sources.
4. **How do I undo it?** — the rollback plan, pre-written.

If the card can't answer all four, the change should not have reached a human — it should
have escalated or been broadened. **The card is a promise that the homework is done.**

## Anatomy

```
┌────────────────────────────────────────────────────────────┐
│ ⚠ ROUTE-TO-OWNER · #inc-4821 · block egress to 185.x.x.x    │  ← header: gate + why-routed
├────────────────────────────────────────────────────────────┤
│ ACTION   block-domain  →  fw-prod-edge-1                     │  ← typed action from catalog
│          "Block outbound to 185.220.101.0/24 at edge FW"    │
├────────────────────────────────────────────────────────────┤
│ RISK ENVELOPE                                                │
│   blast radius   ▓▓░░░  2 services, 0 tier-0   (graph)       │  ← every score shows its source
│   reversibility  ✓ reversible — auto-expires 4h  (catalog)  │
│   environment    ● prod                          (metadata) │
│   confidence     ▓▓▓▓░  acting 0.86 / audit 0.71 (LLM+audit)│  ← divergence shown, not hidden
├────────────────────────────────────────────────────────────┤
│ WHY                                                          │
│   C2 beacon to 185.220.101.4 every 60s from web-03.         │
│   Matches runbook "egress-block on confirmed C2" §3.        │  ← grounded, cited, collapsible
│   ▸ sources: alert #4821 · runbook RB-12 · netflow          │
├────────────────────────────────────────────────────────────┤
│ ROLLBACK   remove-fw-rule fw-prod-edge-1 rule#auto-4821     │
│            (or wait — rule auto-expires in 4h)               │
├────────────────────────────────────────────────────────────┤
│ [ Approve ]  [ Approve + widen scope ]  [ Reject ]  [ Ask ]  │  ← decision, not a form
└────────────────────────────────────────────────────────────┘
```

## Design rules (each one earns its place)

- **Every risk score names its source.** `blast_radius (graph)`, `reversibility
  (catalog)`, `environment (metadata)`, `confidence (LLM + audit)`. This is the visible
  proof of the deterministic/LLM boundary from [policy-engine.md](policy-engine.md): the
  owner can see that what *opened* the gate was measured, and only the narrative and
  confidence came from a model.
- **Show acting-vs-audit confidence side by side.** Never a single blended number. When
  the [independent audit agent](objectives.md) diverges from the acting agent, the owner
  sees the disagreement — that's a safety feature, not a blemish to hide. Wide divergence
  should have escalated before it ever reached the card; if it's here, it's flagged.
- **Reasoning is grounded and cited, never free text.** Every "why" links to the alert,
  the runbook section, the netflow. Ungrounded reasoning is a smell. Sources are one tap
  away but collapsed by default — complete, not cluttered.
- **Rollback is shown before the buttons, always populated.** No undo plan → the change
  never became a card (see the non-negotiable: *every write has a rollback*). Where the
  action self-reverses (auto-expiring rule), say so — it lowers the stakes of a yes.
- **The card is a decision, not a form.** Four actions, no free-text-required fields:
  **Approve**, **Approve + widen scope**, **Reject**, **Ask** (send a question back to the
  agent without deciding). Optional note on reject/ask. Speed is a safety property — a
  slow card gets rubber-stamped.
- **"Approve + widen scope" exists because narrow is the default.** The agent proposes the
  *minimum* action; owners with more context can safely broaden ("block the whole /24, not
  just the one IP"). Widening is a human privilege, never an agent one.
- **Poison-aware by construction.** Doc-sourced reasoning is visibly labeled as context,
  and the card states plainly that context *raised* caution and could never have *lowered*
  the gate. The owner is never asked to trust a runbook's authority — only its information.

## Failure & edge states the card must handle

| State | What the owner sees | Why |
|---|---|---|
| Unknown/uncatalogued action | Card refuses to render as auto-approvable; shows "novel action — manual review" | The catalog is the safety boundary; the card must not imply a clean approval exists |
| Low owner-confidence | "Routed to you at 0.6 confidence — are you the right owner?" + reassign | Stale/ambiguous ownership is dangerous; make correcting it a first-class action |
| Stale change | "Proposed 22m ago — posture may have shifted" + re-validate | Time decays the risk read; don't let an old plan execute on new reality |
| Audit-agent divergence over threshold | Escalation banner, not an approve button | Divergence is a deterministic escalation trigger, not a judgment call for the owner |

## What "best in the industry" means here

Incumbents route to a **role/queue** and show **one confidence number**. The Assent card
routes to the **authoritative owner**, shows a **multi-variable envelope with provenance**,
surfaces **audit disagreement**, and guarantees a **rollback** — the four things the market
demonstrably doesn't do (see [competitive-landscape.md](competitive-landscape.md)). The
card is where the whole thesis becomes something a person can hold in one hand.

## The feedback loop
Every card action is graph fuel. **Approve/reject** confirms or corrects the ownership
edge (see [graph-strategy.md](graph-strategy.md) tier 6). **Reassign** repairs routing at
the source. **Widen/narrow** teaches the catalog what a safe default scope looks like.
Normal use makes the next card better — the card isn't just where trust is spent, it's
where it compounds.
