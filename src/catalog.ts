/**
 * The action catalog — the safety boundary.
 *
 * Deterministic reversibility and effect (read vs. write) require every action
 * to be pre-classified. An action type NOT in this catalog is unknown risk and
 * fails safe to a human (docs/policy-engine.md — "The action catalog is the
 * safety boundary"). Coverage is a build cost we pay deliberately: the system
 * can never auto-execute an action whose risk it has not been taught.
 *
 * Only two properties live here: whether the action mutates state, and its
 * intrinsic reversibility. Blast radius and environment are properties of the
 * *target*, not the action type, and are computed elsewhere from graph/metadata.
 */

import { Effect, Reversibility } from "./types.ts";

export interface CatalogEntry {
  effect: Effect;
  /**
   * Intrinsic reversibility of the action type. This is the maximum
   * reversibility the action can have; a specific target can only lower it.
   */
  reversibility: Reversibility;
  /** The catalogued action type that undoes this one, if any. */
  inverse?: string;
  description: string;
}

/**
 * A small, representative catalog. Real deployments grow this; the point is
 * that the classification is code — versioned, reviewable, testable — not an
 * LLM opinion at decision time.
 */
export const ACTION_CATALOG: Readonly<Record<string, CatalogEntry>> = Object.freeze({
  // ---- reads: always autonomous ----
  "get-host-posture": {
    effect: Effect.Read,
    reversibility: Reversibility.Reversible,
    description: "Read security posture of a host.",
  },
  "list-vulnerabilities": {
    effect: Effect.Read,
    reversibility: Reversibility.Reversible,
    description: "Enumerate known vulnerabilities for a target.",
  },

  // ---- reversible writes: auto-eligible when narrow + non-prod ----
  "block-domain": {
    effect: Effect.Write,
    reversibility: Reversibility.Reversible,
    inverse: "unblock-domain",
    description: "Add a domain to the network blocklist.",
  },
  "unblock-domain": {
    effect: Effect.Write,
    reversibility: Reversibility.Reversible,
    inverse: "block-domain",
    description: "Remove a domain from the network blocklist.",
  },
  "isolate-host": {
    effect: Effect.Write,
    reversibility: Reversibility.Reversible,
    inverse: "unisolate-host",
    description: "Network-isolate a host via EDR.",
  },
  "unisolate-host": {
    effect: Effect.Write,
    reversibility: Reversibility.Reversible,
    inverse: "isolate-host",
    description: "Restore a host's network connectivity.",
  },
  "disable-user": {
    effect: Effect.Write,
    reversibility: Reversibility.Reversible,
    inverse: "enable-user",
    description: "Disable a user account.",
  },
  "enable-user": {
    effect: Effect.Write,
    reversibility: Reversibility.Reversible,
    inverse: "disable-user",
    description: "Re-enable a user account.",
  },

  // ---- partially reversible: undo is manual/lossy ----
  "rotate-credential": {
    effect: Effect.Write,
    reversibility: Reversibility.PartiallyReversible,
    description: "Rotate a secret/credential; consumers must be updated.",
  },
  "revoke-token": {
    effect: Effect.Write,
    reversibility: Reversibility.PartiallyReversible,
    description: "Revoke an access token; cannot be un-revoked.",
  },

  // ---- irreversible: never auto-eligible ----
  "delete-volume": {
    effect: Effect.Write,
    reversibility: Reversibility.Irreversible,
    description: "Permanently delete a storage volume.",
  },
  "terminate-instance": {
    effect: Effect.Write,
    reversibility: Reversibility.Irreversible,
    description: "Terminate a compute instance.",
  },
});

export function lookupAction(type: string): CatalogEntry | undefined {
  return ACTION_CATALOG[type];
}

export function isCatalogued(type: string): boolean {
  return Object.prototype.hasOwnProperty.call(ACTION_CATALOG, type);
}
