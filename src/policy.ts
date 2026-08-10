/**
 * The policy engine — the moat.
 *
 * `policy()` is a pure, deterministic function of the risk envelope, the owner,
 * and a few measured facts about the change. It IS the trust decision, so it is
 * code: auditable, testable, versioned (docs/decisions.md — D2, D6).
 *
 * The single invariant it enforces (docs/policy-engine.md):
 *
 *   The LLM may produce any input that only makes the gate MORE conservative.
 *   Anything that could RELAX the gate must be deterministic.
 *
 * Concretely, auto-execution is earned by a LOW RISK ENVELOPE (reversible +
 * narrow + non-prod) — never by high confidence. Confidence and doc-grounded
 * context can only tighten.
 */

import {
  BlastRadius,
  Confidence,
  Decision,
  Effect,
  Environment,
  type PolicyResult,
  Reversibility,
} from "./types.ts";

/**
 * The autonomy dial. Autonomy is earned per customer, not a launch default
 * (docs/objectives.md, roadmap Phase 3). With `writesMayAutoExecute: false`
 * (the safe default), every write gates and only reads run autonomously.
 */
export interface AutonomyDial {
  /** Master switch for auto-executing writes. Default: false. */
  writesMayAutoExecute: boolean;
  /** Widest blast radius still eligible for auto-execution. */
  maxAutoBlastRadius: BlastRadius;
  /** Environments in which writes may auto-execute. Prod is never included. */
  autoEnvironments: ReadonlySet<Environment>;
}

/** The conservative default dial: reads auto, all writes gate. */
export const DEFAULT_DIAL: AutonomyDial = Object.freeze({
  writesMayAutoExecute: false,
  maxAutoBlastRadius: BlastRadius.Narrow,
  autoEnvironments: new Set([Environment.Dev, Environment.Staging]),
});

/**
 * The measured, deterministic inputs the policy function decides on. Everything
 * here is either graph/metadata-derived or a tighten-only signal — nothing the
 * model asserts can open the gate.
 */
export interface PolicyInput {
  effect: Effect; // catalog: read vs write
  actionCatalogued: boolean; // false => unknown action => fail safe
  blastRadius: BlastRadius; // graph
  reversibility: Reversibility; // catalog + target
  environment: Environment; // target metadata
  confidence: Confidence; // LLM, tighten-only
  ownerResolved: boolean; // graph
  ownerConfidence: Confidence; // graph edge confidence, tighten-only
  hasRollback: boolean; // write with no rollback => never auto
  /** Independent audit agent disagrees with the acting agent beyond threshold. */
  auditDivergence: boolean;
  /** Doc-grounded cautions. Tighten-only: presence can gate, absence never opens. */
  contextCautions: number;
}

const BLAST_ORDER: Record<BlastRadius, number> = {
  [BlastRadius.Narrow]: 0,
  [BlastRadius.Moderate]: 1,
  [BlastRadius.Wide]: 2,
};

function withinBlast(actual: BlastRadius, max: BlastRadius): boolean {
  return BLAST_ORDER[actual] <= BLAST_ORDER[max];
}

/**
 * The pure trust decision. Reason strings record every gate that fired so the
 * outcome is fully explainable and testable.
 *
 * Decision ordering is fail-safe: any single conservative trigger dominates.
 * The function only reaches AutoExecute after clearing *every* gate.
 */
export function policy(input: PolicyInput, dial: AutonomyDial = DEFAULT_DIAL): PolicyResult {
  const reasons: string[] = [];

  // Reads are autonomous. The real trust boundary is read vs. write.
  // A read must still be a known action; an unknown action is unknown risk.
  if (input.effect === Effect.Read) {
    if (!input.actionCatalogued) {
      return { decision: Decision.Escalate, reasons: ["unknown-action:fail-safe"] };
    }
    return { decision: Decision.AutoExecute, reasons: ["read:autonomous"] };
  }

  // ----- everything below is a WRITE -----

  // Fail-safe: an action the catalog has never classified has unknown risk.
  if (!input.actionCatalogued) {
    return { decision: Decision.Escalate, reasons: ["unknown-action:fail-safe"] };
  }

  // Independent audit disagreement is itself a deterministic escalation trigger.
  if (input.auditDivergence) {
    return { decision: Decision.Escalate, reasons: ["audit-divergence:escalate"] };
  }

  // No safe place to send it: unresolved or low-confidence ownership must never
  // be silently auto-routed. Missing data degrades to "ask a human".
  if (!input.ownerResolved) {
    return { decision: Decision.Escalate, reasons: ["owner-unresolved:escalate"] };
  }
  if (input.ownerConfidence === Confidence.Low) {
    return { decision: Decision.Escalate, reasons: ["owner-low-confidence:escalate"] };
  }

  // From here the fallback is a human owner's assent (RouteToOwner). We only
  // *downgrade* to AutoExecute if the change clears the full low-envelope bar.
  // Collect the reasons auto-execution is or isn't available.

  // Confidence is tighten-only: low confidence forces a human, but high
  // confidence is NEVER what authorizes auto-execution.
  const confidenceBlocksAuto = input.confidence === Confidence.Low;
  if (confidenceBlocksAuto) reasons.push("low-confidence:no-auto");

  // Context (untrusted docs) may only raise caution. Any doc-grounded caution
  // removes auto-eligibility; it can never lower the gate.
  const contextBlocksAuto = input.contextCautions > 0;
  if (contextBlocksAuto) reasons.push("context-caution:no-auto");

  // No rollback on a write => no autonomy, ever.
  if (!input.hasRollback) reasons.push("no-rollback:no-auto");

  // The envelope must be genuinely low: reversible + narrow-enough + non-prod.
  // These are the measured properties an attacker cannot fake.
  const reversibleEnough = input.reversibility === Reversibility.Reversible;
  if (!reversibleEnough) reasons.push("not-reversible:no-auto");

  const nonProd =
    input.environment !== Environment.Prod && input.environment !== Environment.Unknown;
  if (!nonProd) reasons.push("prod-or-unknown-env:no-auto");

  const blastOk = withinBlast(input.blastRadius, dial.maxAutoBlastRadius);
  if (!blastOk) reasons.push("blast-too-wide:no-auto");

  const envAllowed = dial.autoEnvironments.has(input.environment);
  if (!envAllowed) reasons.push("env-not-in-dial:no-auto");

  const dialOn = dial.writesMayAutoExecute;
  if (!dialOn) reasons.push("autonomy-dial-off:no-auto");

  const autoEligible =
    dialOn &&
    !confidenceBlocksAuto &&
    !contextBlocksAuto &&
    input.hasRollback &&
    reversibleEnough &&
    nonProd &&
    blastOk &&
    envAllowed;

  if (autoEligible) {
    return { decision: Decision.AutoExecute, reasons: ["low-envelope:earned-auto"] };
  }

  reasons.push("route-to-owner:human-assent");
  return { decision: Decision.RouteToOwner, reasons };
}
