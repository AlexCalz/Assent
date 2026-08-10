/**
 * Tests for the engine: catalog normalization, effective-reversibility clamp,
 * audit divergence, and end-to-end evaluation of realistic Change objects.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  auditDiverges,
  evaluate,
  mostConservativeReversibility,
} from "../src/engine.ts";
import { type AutonomyDial } from "../src/policy.ts";
import {
  BlastRadius,
  type Change,
  Confidence,
  Decision,
  Environment,
  Reversibility,
} from "../src/types.ts";

const EARNED_DIAL: AutonomyDial = {
  writesMayAutoExecute: true,
  maxAutoBlastRadius: BlastRadius.Narrow,
  autoEnvironments: new Set([Environment.Dev, Environment.Staging]),
};

function blockDomainChange(overrides: Partial<Change> = {}): Change {
  return {
    action: { type: "block-domain", target: "evil.example.com" },
    reasoning: "C2 domain observed beaconing from staging host.",
    riskEnvelope: {
      blastRadius: BlastRadius.Narrow,
      reversibility: Reversibility.Reversible,
      environment: Environment.Staging,
      confidence: Confidence.High,
    },
    owner: { id: "team-netsec", confidence: Confidence.High, source: "CODEOWNERS" },
    rollback: {
      action: { type: "unblock-domain", target: "evil.example.com" },
      description: "Remove the domain from the blocklist.",
    },
    ...overrides,
  };
}

test("realistic reversible+narrow+staging block auto-executes under earned dial", () => {
  const r = evaluate(blockDomainChange(), { dial: EARNED_DIAL });
  assert.equal(r.decision, Decision.AutoExecute);
});

test("same change in prod routes to the owner", () => {
  const change = blockDomainChange();
  change.riskEnvelope.environment = Environment.Prod;
  const r = evaluate(change, { dial: EARNED_DIAL });
  assert.equal(r.decision, Decision.RouteToOwner);
});

test("a read action auto-executes regardless of dial", () => {
  const change = blockDomainChange({
    action: { type: "get-host-posture", target: "host-42" },
    rollback: null,
  });
  const r = evaluate(change); // default (conservative) dial
  assert.equal(r.decision, Decision.AutoExecute);
});

test("uncatalogued action fails safe to escalation", () => {
  const change = blockDomainChange({
    action: { type: "reformat-the-datacenter", target: "everything" },
  });
  const r = evaluate(change, { dial: EARNED_DIAL });
  assert.equal(r.decision, Decision.Escalate);
  assert.ok(r.reasons.includes("unknown-action:fail-safe"));
});

test("irreversible catalog action never auto-executes even if envelope claims reversible", () => {
  // The Change *claims* the target is reversible, but the catalog knows
  // delete-volume is irreversible. The conservative clamp must win.
  const change = blockDomainChange({
    action: { type: "delete-volume", target: "vol-1" },
    riskEnvelope: {
      blastRadius: BlastRadius.Narrow,
      reversibility: Reversibility.Reversible, // a lie / mistake upstream
      environment: Environment.Staging,
      confidence: Confidence.High,
    },
    rollback: null,
  });
  const r = evaluate(change, { dial: EARNED_DIAL });
  assert.notEqual(r.decision, Decision.AutoExecute);
  assert.ok(r.reasons.includes("not-reversible:no-auto"));
});

test("missing rollback on a write blocks auto and routes to owner", () => {
  const r = evaluate(blockDomainChange({ rollback: null }), { dial: EARNED_DIAL });
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("no-rollback:no-auto"));
});

test("audit agent divergence escalates an otherwise auto-eligible change", () => {
  const r = evaluate(blockDomainChange(), {
    dial: EARNED_DIAL,
    auditConfidence: Confidence.Low, // acting said High; gap > 1 step
  });
  assert.equal(r.decision, Decision.Escalate);
  assert.ok(r.reasons.includes("audit-divergence:escalate"));
});

test("audit agent within one step does not escalate", () => {
  const r = evaluate(blockDomainChange(), {
    dial: EARNED_DIAL,
    auditConfidence: Confidence.Medium, // one step from High
  });
  assert.equal(r.decision, Decision.AutoExecute);
});

test("poisoned-doc caution can gate but never opens the gate", () => {
  const change = blockDomainChange({
    context: { cautions: ["runbook: this domain fronts a partner integration"] },
  });
  const r = evaluate(change, { dial: EARNED_DIAL });
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("context-caution:no-auto"));
});

test("unresolved owner escalates", () => {
  const r = evaluate(blockDomainChange({ owner: null }), { dial: EARNED_DIAL });
  assert.equal(r.decision, Decision.Escalate);
});

// ---- unit tests for the helpers ----

test("auditDiverges: true only beyond one ordinal step", () => {
  assert.equal(auditDiverges(Confidence.High, Confidence.Low), true);
  assert.equal(auditDiverges(Confidence.High, Confidence.Medium), false);
  assert.equal(auditDiverges(Confidence.Medium, Confidence.Medium), false);
});

test("mostConservativeReversibility picks the less reversible of two", () => {
  assert.equal(
    mostConservativeReversibility(Reversibility.Reversible, Reversibility.Irreversible),
    Reversibility.Irreversible,
  );
  assert.equal(
    mostConservativeReversibility(
      Reversibility.PartiallyReversible,
      Reversibility.Reversible,
    ),
    Reversibility.PartiallyReversible,
  );
});
