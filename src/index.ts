/**
 * Assent policy kernel — public surface.
 *
 * This is the deterministic core the concept docs designate as the moat: the
 * `Change` primitive plus the pure `policy()` decision function, wired by
 * `evaluate()`. Diagnosis (LLM) sits upstream and enforcement (an existing
 * gateway) sits downstream; only the trust decision lives here.
 */

export * from "./types.ts";
export { ACTION_CATALOG, isCatalogued, lookupAction, type CatalogEntry } from "./catalog.ts";
export {
  type AutonomyDial,
  DEFAULT_DIAL,
  policy,
  type PolicyInput,
} from "./policy.ts";
export {
  auditDiverges,
  evaluate,
  type EvaluateOptions,
  mostConservativeReversibility,
} from "./engine.ts";
