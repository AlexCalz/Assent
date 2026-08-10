/**
 * Core types for the Assent policy kernel.
 *
 * These encode the product's central primitive (docs/objectives.md):
 *
 *   Change { action, reasoning, risk_envelope, owner, rollback }
 *   PolicyEngine( risk_envelope, owner ) -> { auto | route | escalate }
 *
 * The type boundary here *is* the trust boundary. Fields that can only ever
 * make the gate MORE conservative (confidence, context flags) are separated
 * from fields that can OPEN the gate (blast radius, reversibility,
 * environment, owner). See docs/policy-engine.md — "The invariant".
 */

// ---------------------------------------------------------------------------
// Deterministic, gate-opening variables — must be MEASURED, never opined.
// ---------------------------------------------------------------------------

/** Whether the action reads state or mutates it. The real trust boundary. */
export const Effect = {
  Read: "read",
  Write: "write",
} as const;
export type Effect = (typeof Effect)[keyof typeof Effect];

/**
 * Reversibility of a write, pre-classified per action type in the catalog.
 * An attacker cannot fake this — it is a property of the action, not a claim.
 */
export const Reversibility = {
  /** A clean, automatic undo exists (e.g. block-domain -> unblock-domain). */
  Reversible: "reversible",
  /** Undo is partial, manual, or lossy (e.g. rotate-credential). */
  PartiallyReversible: "partially_reversible",
  /** No undo (e.g. delete-volume, terminate-instance). Never auto-eligible. */
  Irreversible: "irreversible",
} as const;
export type Reversibility = (typeof Reversibility)[keyof typeof Reversibility];

/** Deployment environment of the target, from target metadata (not the model). */
export const Environment = {
  Dev: "dev",
  Staging: "staging",
  Prod: "prod",
  /** Environment could not be determined -> treated as most conservative. */
  Unknown: "unknown",
} as const;
export type Environment = (typeof Environment)[keyof typeof Environment];

/**
 * Blast radius = how much the action can affect, measured from the graph
 * (systems/users touched, whether the target is tier-0). Ordinal: higher is
 * wider. Deterministic — this can OPEN the gate, so it is never model-opined.
 */
export const BlastRadius = {
  /** Single non-critical target, no downstream fan-out. */
  Narrow: "narrow",
  /** A bounded group of systems/users. */
  Moderate: "moderate",
  /** Many systems/users, or a tier-0 / shared dependency. */
  Wide: "wide",
} as const;
export type BlastRadius = (typeof BlastRadius)[keyof typeof BlastRadius];

// ---------------------------------------------------------------------------
// Confidence — LLM-produced. May ONLY tighten the gate, never open it.
// ---------------------------------------------------------------------------

/**
 * Confidence is produced by the acting agent and cross-checked by the audit
 * agent. Per docs/policy-engine.md it *only ever raises caution*: low
 * confidence can force escalation, but high confidence never authorizes
 * auto-execution. This is the deliberate inversion of "99% confidence -> act".
 */
export const Confidence = {
  Low: "low",
  Medium: "medium",
  High: "high",
} as const;
export type Confidence = (typeof Confidence)[keyof typeof Confidence];

// ---------------------------------------------------------------------------
// The risk envelope.
// ---------------------------------------------------------------------------

export interface RiskEnvelope {
  blastRadius: BlastRadius; // deterministic (graph)
  reversibility: Reversibility; // deterministic (catalog)
  environment: Environment; // deterministic (target metadata)
  confidence: Confidence; // LLM-produced — tighten-only
}

// ---------------------------------------------------------------------------
// Actions & ownership.
// ---------------------------------------------------------------------------

/**
 * A typed, normalized action. Step 2 of the pipeline forces the LLM's free-form
 * proposal into one of these; an action type absent from the catalog fails safe
 * to escalation (docs/policy-engine.md — "The action catalog is the safety
 * boundary").
 */
export interface Action {
  type: string; // must exist in the catalog
  target: string; // opaque target id (system/resource)
  params?: Record<string, unknown>;
}

/** Resolved owner of the affected stack, with provenance confidence. */
export interface Owner {
  id: string;
  /** Confidence in the ownership edge itself (graph corroboration/staleness). */
  confidence: Confidence;
  source?: string;
}

/**
 * Context flags derived from internal docs (runbooks, postmortems). These are
 * UNTRUSTED input: they may only raise caution and can never lower a gate below
 * its policy floor (docs/objectives.md — "Context raises caution, never grants
 * permission"). Modeled as tighten-only signals.
 */
export interface ContextFlags {
  /** A doc-grounded reason this specific change is riskier than its envelope. */
  cautions: string[];
}

// ---------------------------------------------------------------------------
// The Change primitive.
// ---------------------------------------------------------------------------

export interface Change {
  action: Action;
  /** Human-readable "why", grounded in internal docs. Explains, never decides. */
  reasoning: string;
  riskEnvelope: RiskEnvelope;
  owner: Owner | null; // null => unresolved => escalate
  /** The undo plan. No rollback on a write => never auto-eligible. */
  rollback: RollbackPlan | null;
  context?: ContextFlags;
}

export interface RollbackPlan {
  /** The inverse action that restores prior state. */
  action: Action;
  description: string;
}

// ---------------------------------------------------------------------------
// The decision.
// ---------------------------------------------------------------------------

export const Decision = {
  /** Earned, low-envelope write (or any read): execute without a human. */
  AutoExecute: "auto_execute",
  /** Route the approval to the authoritative owner of the affected stack. */
  RouteToOwner: "route_to_owner",
  /** No safe owner / too risky / fail-safe: send up for human judgement. */
  Escalate: "escalate",
} as const;
export type Decision = (typeof Decision)[keyof typeof Decision];

export interface PolicyResult {
  decision: Decision;
  /**
   * Machine-readable reasons the decision came out this way. Every gate that
   * fired is recorded, so the decision is fully auditable and testable.
   */
  reasons: string[];
}
