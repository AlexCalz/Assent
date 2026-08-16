# Decision Log

Running record of key calls and *why*. Newest at top.

## D11 — Incorporate TRIDENT-AI surfaces; keep Assent's gate
**Decision:** Build the operable dashboard by taking the IA TRIDENT-AI proved useful
(agent roster, incident package, remediation panel, audit trail, demo inject,
three-column ops layout, dual deploy profiles) and grounding every gate-relevant fact
in Assent's measured envelope + ownership graph. Confidence is displayed (Trident-style
gauge) but still never authorizes (D6). Remediation is a single gated `Change`, not a
free-form MCP option list. MITRE / business-impact narrative is contextual display only.
**Why:** Assent and TRIDENT are on the same path — agentic investigation → HITL
remediation — but Assent's wedge is *graded, ownership-routed, risk-to-act gating*.
Borrowing Trident's presentation without adopting its "approve any MCP tool call"
model lets us ship a familiar SOC surface while keeping the deterministic moat.
Also closes the prior dashboard ask: one shell for Cloud Personal/Startup and Private
Tenant/Agency via an environment strip + profile switcher.

## D10 — Build the product: a runnable control plane, not a library
**Decision:** Assemble the parts into an operable application. Adds the four missing
layers — `inventory.py` (measured environment / blast-radius / tier-0 facts),
`proposer.py` (signal → typed catalog action), `executor.py` (the hand-off seam to real
enforcement, per D5), `ledger.py` (hash-chained, tamper-evident audit trail) — plus
`runtime.py` (the `Assent` orchestrator: submit → propose → resolve owner → audit →
gate → act or queue, with approve/deny/rollback) and `app.py` (a stdlib HTTP app with a
working approval queue). Skips the read-only Overview page and Phase-0 customer
interviews as a sequencing call.
**Why:** every safety property was real but unusable — changes were hand-constructed in
examples and nothing could actually *run*. Two hand-waves in particular were load-
bearing and are now closed: risk facts come from an inventory (unknown system ⇒
assume prod + tier-0, so it cannot auto-execute), and actions come from a playbook that
refuses to propose anything the catalog can't classify. The ledger answers the
"accountability" trust blocker from vision.md with tamper-evidence rather than a log
file. The graph flywheel is now real: approving in the UI writes an ownership claim.

## D9 — Independent audit agent as a deterministic escalation trigger
**Decision:** Add the audit agent (`assent/audit.py`): an `AuditAgent` interface plus a
deterministic `RuleBasedAuditor` that derives its *own* confidence from measured facts,
never reading the acting agent's number. The *decision* about a disagreement stays in
the policy engine: `evaluate(change, audit=...)` escalates on dissent or on
acting-vs-audit divergence beyond a threshold, and otherwise takes the more conservative
of the two confidences. The audit signal can only ever tighten the gate.
**Why:** objectives.md makes the second opinion a first-class safety property, and
policy-engine.md specifies divergence as a deterministic escalation. Keeping the auditor
independent (its own read) is what makes it a real check rather than an echo of a
poisonable number; keeping the *response* in the deterministic engine keeps the trust
decision auditable. In the demo this immediately caught a prod tier-0 credential
rotation the envelope alone would have routed, and escalated it.

## D8 — Build out to a full slice: graph resolver + approval card on the engine
**Decision:** Extend the deterministic core with two pieces, in order: (1) the ownership
graph resolver (`assent/graph.py`) — the source ladder, confidence-scored edges,
corroboration up / staleness down, resolving JIT per change; (2) the approval-card
renderer (`assent/approval_card.py`) — the "hero component," rendered from *real*
`PolicyResult` output. `examples/render_cards.py` wires all three end-to-end.
**Why:** The resolver was already the engine's most-hand-waved input (a plain `Owner`);
making it real closes the "unknown owner → escalate" safety story with actual decay/
corroboration math (graph-strategy.md), and gives the card a truthful owner + confidence
to display. The card was the top remaining `next-to-explore` item and the thing that
makes the whole thesis legible: it shows the audit trail the engine produced, and by
construction only *displays* the gate — it can't change it. LLM-produced reasoning is
HTML-escaped (untrusted-input hygiene, consistent with the poisoned-doc rule).

## D7 — First code is the deterministic policy engine, not the agents
**Decision:** The first product code is a dependency-free reference implementation of
the `Change` primitive + `PolicyEngine` pure function (`assent/`), with an invariant
test suite. The LLM-facing pieces stay on paper for now.
**Why:** The moat is the *decision*, not the agents (D2), and `policy-engine.md` says
that decision "must be code: auditable, testable, versioned." Materializing it first
makes every safety invariant executable — D6 ("confidence only tightens"), "no rollback
→ no autonomy," "context raises caution, never permission," "unknown owner → escalate"
are now tests that fail loudly if broken — before any agent or integration exists to
muddy it. Cheapest possible way to prove the core holds together.

## D6 — Policy engine boundary: "LLM may only tighten the gate"
**Decision:** Invariant — the LLM may produce any input that only makes the gate *more*
conservative; anything that could *relax* it (blast radius, reversibility, environment,
owner authority, the policy function itself) is deterministic. Auto-execution is earned
by a **low risk envelope, never by high confidence.** Confidence only escalates.
**Why:** LLM confidence is miscalibrated and poisonable; measured properties (reversible
+ narrow + non-prod) can't be faked. This is the defensible break from Dropzone's
"99% confidence → act." See [policy-engine.md](policy-engine.md).

## D5 — Ride on existing enforcement; we compute the decision
**Decision:** Don't build enforcement (gateways/policy engines exist — Prisma AIRS,
Microsoft Agent Governance Toolkit, Silverfort, MCP gateways). Assent computes the
gating *decision* (envelope + owner + doc-grounded assessment) and hands it to an
existing gateway to enforce.
**Why:** Aug 2026 web-check: enforcement is now commodity/consensus; graded +
ownership-routed + doc-grounded *decisioning* is the open white space. Converts three
competitors into substrate, slashes build. See [competitive-landscape.md](competitive-landscape.md).

## D4 — Name: Assent
**Decision:** Product is named **Assent**.
**Why:** Nothing acts without assent — either an earned policy assent (low-risk, auto)
or a human owner's assent (everything else). The name *is* the product thesis.

## D3 — Populate the graph by "derive, don't demand"
**Decision:** No big-bang integration. Lazy/JIT per-change resolution, a cheap→rich
source ladder (code → ops → cloud → identity → docs → human confirmation), and
confidence-scored edges. Incomplete graph degrades to "ask a human."
**Why:** Security products die on data-integration slogs. This ships at low coverage
and self-improves where the product is active.

## D2 — The core primitive is a gated `Change`, not "an agent"
**Decision:** Product reduces to a `Change` object (action, reasoning, risk_envelope,
owner, rollback) + a deterministic `PolicyEngine` mapping `(risk_envelope, owner)` to
`{auto | route-to-owner | escalate}`.
**Why:** The three refinements (severity-scaled autonomy, doc-grounded risk assessment,
ownership-aware approval) are one object, not three features. The gating engine is the
moat; the agents are the demo.

## D1 — Wedge is the control layer, not the agents
**Decision:** Position as "the control plane for safe agentic *remediation*," not
another AI-SOC analyst.
**Why:** Autonomous triage is crowded and read-only. Autonomous remediation is unsolved
because the trust layer doesn't exist. That trust layer is the white space.

## D0 — Brainstorm before build
**Decision:** Refine concept + capture planning docs before writing product code.
**Why:** The bet is customer-appetite, not technical feasibility. Cheaper to validate
on paper first.
