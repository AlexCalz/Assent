# Decision Log

Running record of key calls and *why*. Newest at top.

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
