# Decision Log

Running record of key calls and *why*. Newest at top.

## D7 — Build the deterministic core first, as an erasable-TS kernel
**Decision:** The first product code is the moat and nothing else: the `Change` primitive
+ the pure `policy()` decision function + the action catalog, with the pipeline steps that
must be deterministic (normalize, envelope, owner-gate, decide). Diagnosis (LLM, upstream)
and enforcement (gateway, downstream per D5) are deliberately *out* of the kernel. Written
in TypeScript that runs directly under Node's type-stripping (no build step, no runtime
deps), tested with the built-in runner — 29 tests, each named for the invariant it
defends.
**Why:** D2/D6 call the policy engine the moat precisely because it must be "auditable,
testable, versioned" — that is a claim you can only make about code. Encoding the D6
invariant as a pure function with a test that proves "high confidence never opens the gate"
(the anti-Dropzone case) turns the thesis from a doc into something executable. Keeping the
LLM and the gateway outside the kernel keeps the trust decision small and deterministic.

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
