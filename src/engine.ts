/**
 * The engine wires the pipeline together (docs/policy-engine.md — "The
 * pipeline"): a proposed Change is normalized against the catalog, its envelope
 * is measured deterministically, ownership is taken as resolved input, the
 * independent audit read is compared, and the pure `policy()` function decides.
 *
 * Steps 1 (diagnose/propose) and 6 (enforce) live outside this kernel: an LLM
 * produces the Change upstream, and an existing gateway enforces the decision
 * downstream (docs/decisions.md — D5, "ride on enforcement"). What lives here
 * is exactly the part that must be deterministic: computing the decision.
 */

import { lookupAction } from "./catalog.ts";
import { policy, type AutonomyDial, DEFAULT_DIAL, type PolicyInput } from "./policy.ts";
import {
  type Change,
  Confidence,
  Decision,
  Effect,
  type PolicyResult,
  Reversibility,
} from "./types.ts";

export interface EvaluateOptions {
  dial?: AutonomyDial;
  /**
   * The independent audit agent's confidence read on the same change. If it
   * diverges from the acting agent's confidence beyond one ordinal step, that
   * disagreement is itself an escalation trigger (docs/objectives.md).
   */
  auditConfidence?: Confidence;
}

const CONF_ORDER: Record<Confidence, number> = {
  [Confidence.Low]: 0,
  [Confidence.Medium]: 1,
  [Confidence.High]: 2,
};

/** Divergence beyond a single ordinal step between acting and audit reads. */
export function auditDiverges(acting: Confidence, audit: Confidence): boolean {
  return Math.abs(CONF_ORDER[acting] - CONF_ORDER[audit]) > 1;
}

/**
 * Evaluate a proposed Change into a policy decision.
 *
 * Note the effective-reversibility clamp: the catalog gives an action type's
 * intrinsic reversibility, but the Change's envelope may declare a *lower*
 * reversibility for this specific target. We take the more conservative of the
 * two — the envelope can tighten, never loosen, the catalog's classification.
 */
export function evaluate(change: Change, opts: EvaluateOptions = {}): PolicyResult {
  const dial = opts.dial ?? DEFAULT_DIAL;
  const entry = lookupAction(change.action.type);

  // Step 2 — normalize. Uncatalogued action => unknown risk => fail safe.
  if (!entry) {
    const input: PolicyInput = {
      effect: Effect.Write, // treat unknown as a write for max caution
      actionCatalogued: false,
      blastRadius: change.riskEnvelope.blastRadius,
      reversibility: change.riskEnvelope.reversibility,
      environment: change.riskEnvelope.environment,
      confidence: change.riskEnvelope.confidence,
      ownerResolved: change.owner !== null,
      ownerConfidence: change.owner?.confidence ?? Confidence.Low,
      hasRollback: change.rollback !== null,
      auditDivergence: false,
      contextCautions: change.context?.cautions.length ?? 0,
    };
    return policy(input, dial);
  }

  // Effective reversibility = min(catalog intrinsic, envelope-declared).
  const effectiveReversibility = mostConservativeReversibility(
    entry.reversibility,
    change.riskEnvelope.reversibility,
  );

  const auditDivergence =
    opts.auditConfidence !== undefined &&
    auditDiverges(change.riskEnvelope.confidence, opts.auditConfidence);

  const input: PolicyInput = {
    effect: entry.effect,
    actionCatalogued: true,
    blastRadius: change.riskEnvelope.blastRadius,
    reversibility: effectiveReversibility,
    environment: change.riskEnvelope.environment,
    confidence: change.riskEnvelope.confidence,
    ownerResolved: change.owner !== null,
    ownerConfidence: change.owner?.confidence ?? Confidence.Low,
    hasRollback: change.rollback !== null,
    auditDivergence,
    contextCautions: change.context?.cautions.length ?? 0,
  };

  return policy(input, dial);
}

const REV_ORDER: Record<Reversibility, number> = {
  [Reversibility.Reversible]: 2,
  [Reversibility.PartiallyReversible]: 1,
  [Reversibility.Irreversible]: 0,
};

/** Lower ordinal = less reversible = more conservative; we take the min. */
export function mostConservativeReversibility(
  a: Reversibility,
  b: Reversibility,
): Reversibility {
  return REV_ORDER[a] <= REV_ORDER[b] ? a : b;
}

export { Decision };
