# Approval Card — the Hero Component

Every gated `Change` that routes to a human surfaces as one thing: an **approval card.**
It is the product's most-seen surface and the moment trust is won or lost. When Assent
says *"I can't decide this alone — you decide,"* the card is that ask. It must let the
right owner make a correct, confident call in seconds, with zero context-hunting.

Design mandate (objectives #2): **fast, clear, complete.** A rubber-stamp is a failure;
so is a card that sends the owner off to three other tabs to feel safe clicking approve.

## What the card must answer

An owner reading the card should be able to answer five questions without leaving it:

1. **What will happen?** — the exact action, exact target. No paraphrase.
2. **Why?** — the reasoning, grounded in the customer's own docs, with the trigger.
3. **What's the blast radius?** — what breaks if this is wrong.
4. **Can we undo it?** — the rollback plan, stated up front.
5. **Why am *I* being asked?** — why this owner, why now, why it wasn't auto-executed.

If any of the five is missing, the card is incomplete and must fail toward *more*
disclosure, never less.

## Anatomy

The card renders the `Change` primitive directly — one field group per section, top to
bottom in decision order.

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠  ROUTE TO OWNER · risk-to-act: MODERATE                   │  ← gate + envelope tier
│  Block outbound domain  c2.evil.example  on  edge-fw-prod-3  │  ← action + target
├─────────────────────────────────────────────────────────────┤
│  WHY                                                         │
│  Beaconing to c2.evil.example from 4 hosts (see alert #8842).│
│  Runbook "C2 containment" (rev 2026-07) prescribes an        │  ← doc-grounded, cited
│  egress block as first-line containment.                     │
├─────────────────────────────────────────────────────────────┤
│  RISK TO ACT                                                 │
│  blast_radius   4 hosts lose egress to 1 domain  (narrow)    │
│  reversibility  fully reversible — unblock is one action     │  ← the four envelope
│  environment    PROD                                         │     variables, measured
│  confidence     0.86  (audit agent: 0.71 — divergence noted) │
├─────────────────────────────────────────────────────────────┤
│  ROLLBACK                                                    │
│  Remove egress rule; no state change, no restart.  [preview] │
├─────────────────────────────────────────────────────────────┤
│  WHY YOU                                                     │
│  You own edge-fw-prod-3 (CODEOWNERS + PagerDuty on-call).    │  ← ownership provenance
│  Not auto-executed: target is PROD (policy floor).           │  ← why it gated
├─────────────────────────────────────────────────────────────┤
│  [ Approve ]   [ Approve with edits ]   [ Decline ]  [ Ask ] │
└─────────────────────────────────────────────────────────────┘
```

### Section-by-section

- **Header — gate + envelope tier.** The policy engine's decision (`route-to-owner`) and
  the risk-to-act tier, stated first. The owner learns the *stakes* before the detail.
- **Action + target.** Rendered from the typed, catalogued action — never free text.
  The literal command/target that will execute, so approve means approve *this*.
- **Why.** The LLM's risk narrative, with the triggering signal and **citations to the
  internal docs** it grounded in. Citations are load-bearing: they let the owner verify
  the reasoning against a source they trust, and they make a poisoned-doc influence
  *visible* rather than silent.
- **Risk to act.** The four envelope variables shown as measured facts, each labelled
  with its qualitative band. `confidence` shows **both** the acting agent's and the
  **independent audit agent's** read; divergence beyond threshold is flagged inline —
  the card never hides a second opinion.
- **Rollback.** The undo plan, with a preview. No rollback → the change never reaches a
  card as approvable (principle: no undo, no autonomy — and no clean approve either).
- **Why you.** Ownership resolution *with provenance* (which source ladder tiers
  corroborated it) and the reason it gated instead of auto-executing (which policy floor
  it hit). This is the anti-rubber-stamp section: it tells the owner the system's
  routing logic so they can catch a mis-route.

## Interaction model

Four actions, matched to what an owner actually needs:

| Control | Meaning | Effect |
|---|---|---|
| **Approve** | Assent to *this exact* change | Hands the change to the enforcement gateway; owner identity + timestamp recorded |
| **Approve with edits** | The intent is right, a param is wrong | Owner adjusts catalogued params only; **re-runs the policy engine** on the edited change before executing |
| **Decline** | No | Change is killed; reason captured, fed back as a labelled negative example |
| **Ask** | Not enough to decide | Threaded question back to the acting agent; card stays open, updates in place |

### Non-negotiable interaction rules

- **Approve with edits re-gates.** An owner-edited change is a *new* change through the
  same deterministic policy engine — editing can never smuggle an action past the gate.
  If the edit widens blast radius past the owner's authority, the card itself escalates.
- **Edits are confined to the catalogued action's typed params.** No free-text command
  injection into an approved change. The action catalog is the safety boundary here too.
- **Decline is one click, and it teaches.** Declining must be as fast as approving —
  otherwise the card biases toward approval. Every decline is a labelled signal.
- **The card is not an instruction sink.** Nothing an owner types in **Ask** is executed
  as a command; it is a question to the agent, which replies with an updated *plan*.
  (Untrusted-data-is-never-an-instruction, applied to the human channel too.)
- **Timeout degrades safely.** No response within the change's SLA → **escalate/broaden**
  (notify a backup owner, raise visibility), **never** auto-approve on silence. Silence
  is not assent.

## How the card defends the thesis

The card is where three of Assent's differentiators become tangible to a buyer:

- **Graded risk-to-act** is *visible* — four labelled variables, not one confidence
  number. The owner sees *why* it's moderate, not just that a model felt unsure.
- **Ownership-aware routing** is *legible* — "Why you," with provenance, is a section no
  queue-based tool can render, because it routes to a role, not an owner.
- **Doc-grounded, poisoning-aware reasoning** is *auditable* — citations let the owner
  check the ground truth, and the confidence inversion is stated plainly: this gated
  because it's **PROD**, not because the model was unsure. High confidence would not have
  opened this gate; only a low envelope does.

## Open design questions

- **Batching / alert fatigue.** During a broad incident one owner may get many cards.
  Group by owner + action type? Risk: batching invites bulk-approve, the exact
  rubber-stamp we forbid. Likely answer: group for *context*, still require per-change
  assent on anything touching prod.
- **Delegation & escalation UX.** "Not mine — reassign to X" as a first-class control,
  which also *corrects an ownership edge* (feeds the graph flywheel).
- **Surface.** Slack/Teams card vs. web app vs. both. Mobile-approvable without losing
  completeness is hard — a phone-sized card must not drop a section to fit.
- **Post-hoc review of auto-executed changes.** Auto-executed low-envelope changes still
  deserve a *reviewable* card (after the fact) so autonomy stays auditable, not silent.
