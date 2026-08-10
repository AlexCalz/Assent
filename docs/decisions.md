# Decision Log

Running record of key calls and *why*. Newest at top.

## D7 — Approval card is the Change primitive, rendered — and it re-gates on edit
**Decision:** The human-facing approval card renders the `Change` object directly (action,
doc-cited reasoning, four-variable envelope, rollback, owner-with-provenance), always shows
the independent audit agent's confidence alongside the acting agent's, and treats **"Approve
with edits" as a new change re-run through the deterministic policy engine.** Silence never
approves — timeout escalates. Decline is one click and teaches.
**Why:** The card is where three differentiators (graded risk-to-act, ownership routing,
doc-grounded reasoning) become tangible to a buyer, and where rubber-stamping must be
designed out. Re-gating on edit keeps the action catalog as the safety boundary even on the
human path; editing can't smuggle an action past the gate. See [approval-card.md](approval-card.md).

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
