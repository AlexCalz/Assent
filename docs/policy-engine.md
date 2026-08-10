# Policy Engine — the Deterministic / LLM Boundary

The policy engine is the moat. Its trustworthiness rests on one invariant.

## The invariant

> **The LLM may produce any input that only makes the gate *more* conservative.
> Anything that could *relax* the gate must be deterministic.**

That single rule assigns every variable to a side of the line: things that can *open*
the gate are measured by code; things that can only *tighten* it may come from a model.

## The pipeline

| Step | Who | Why |
|---|---|---|
| 1. Diagnose & propose action | **LLM** | Reasoning over novel situations — the "why now" of the product |
| 2. Normalize to a typed action from a catalog `{type, target, params}` | **Deterministic** (schema-validated) | Unknown / uncatalogued action → escalate. LLM must emit structured output |
| 3a. `blast_radius` | **Deterministic** (graph: # systems/users affected, is target tier-0) | Can *open* the gate → measured, not opined |
| 3b. `reversibility` | **Deterministic** (pre-classified per action type: block-domain = reversible, delete-volume = not) | Can open the gate → measured |
| 3c. `environment` | **Deterministic** (target metadata: prod/staging/dev) | Can open the gate → measured |
| 3d. `confidence` | **LLM-produced, cross-checked by audit agent** | *Only ever raises caution* — never opens the gate |
| 4. Resolve `owner` (+ confidence) | **Deterministic** (ownership graph) | Routing authority → measured |
| 5. `policy(envelope, owner) -> {auto \| route \| escalate}` | **Deterministic pure function** | This *is* the trust decision — must be code: auditable, testable, versioned |
| 6. Enforce (JIT cred, execute, log, rollback) | **Deterministic / existing gateway** | Ride on Prisma / MCP-gateway substrate |
| Human-readable risk narrative for the approval card | **LLM** | Explains, doesn't decide |

## Two design calls that separate Assent from the incumbents

### 1. Auto-execution is earned by a *low risk envelope*, never by *high confidence*
The sharp break from Dropzone's "99% confidence → act." LLM confidence is badly
calibrated, and an attacker who can poison inputs can manufacture confidence. So
confidence *only escalates* (low → human); it never authorizes. What authorizes
auto-execution is **reversible + narrow + non-prod** — properties you can measure and an
attacker can't fake. Be loud about this inversion; it's the defensible core.

### 2. The action catalog is the safety boundary
Deterministic reversibility / blast-radius requires actions to be pre-classified.
Novel / unknown actions fail safe to human. Coverage is a build cost, but the system can
never auto-execute an action whose risk it hasn't been taught. The independent **audit
agent** computes its own confidence read; divergence beyond a threshold from the acting
agent is itself a deterministic escalation trigger.

## Honest tension
The catalog + graph are where build effort concentrates, and "confidence never opens the
gate" makes Assent's autonomy *narrower* than competitors' marketing — but *trustworthy*
in a way theirs demonstrably isn't (see the 88% incident rate). For a **defense**
product, that's the correct trade.
