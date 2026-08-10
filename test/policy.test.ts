/**
 * Tests for the pure policy() function. Each test names the invariant it
 * defends (docs/objectives.md, docs/policy-engine.md, docs/decisions.md).
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  type AutonomyDial,
  DEFAULT_DIAL,
  policy,
  type PolicyInput,
} from "../src/policy.ts";
import {
  BlastRadius,
  Confidence,
  Decision,
  Effect,
  Environment,
  Reversibility,
} from "../src/types.ts";

/** A write that clears every gate — the one shape eligible for auto. */
function lowEnvelopeWrite(overrides: Partial<PolicyInput> = {}): PolicyInput {
  return {
    effect: Effect.Write,
    actionCatalogued: true,
    blastRadius: BlastRadius.Narrow,
    reversibility: Reversibility.Reversible,
    environment: Environment.Staging,
    confidence: Confidence.High,
    ownerResolved: true,
    ownerConfidence: Confidence.High,
    hasRollback: true,
    auditDivergence: false,
    contextCautions: 0,
    ...overrides,
  };
}

/** A dial with writes-autonomy earned, so auto-execution is reachable at all. */
const EARNED_DIAL: AutonomyDial = {
  writesMayAutoExecute: true,
  maxAutoBlastRadius: BlastRadius.Narrow,
  autoEnvironments: new Set([Environment.Dev, Environment.Staging]),
};

test("reads are autonomous (read vs write is the real boundary)", () => {
  const r = policy({ ...lowEnvelopeWrite(), effect: Effect.Read }, DEFAULT_DIAL);
  assert.equal(r.decision, Decision.AutoExecute);
});

test("default dial gates every write (autonomy is earned, not a default)", () => {
  const r = policy(lowEnvelopeWrite(), DEFAULT_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("autonomy-dial-off:no-auto"));
});

test("earned dial + low envelope => auto-execute", () => {
  const r = policy(lowEnvelopeWrite(), EARNED_DIAL);
  assert.equal(r.decision, Decision.AutoExecute);
});

test("INVARIANT D6: high confidence never opens the gate on a risky envelope", () => {
  // Irreversible, prod, wide blast — but the model is maximally confident.
  // The anti-Dropzone case: "99% confidence -> act" must NOT happen here.
  const r = policy(
    lowEnvelopeWrite({
      confidence: Confidence.High,
      reversibility: Reversibility.Irreversible,
      environment: Environment.Prod,
      blastRadius: BlastRadius.Wide,
    }),
    EARNED_DIAL,
  );
  assert.notEqual(r.decision, Decision.AutoExecute);
});

test("confidence is tighten-only: low confidence removes auto-eligibility", () => {
  const r = policy(lowEnvelopeWrite({ confidence: Confidence.Low }), EARNED_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("low-confidence:no-auto"));
});

test("irreversible writes are never auto-eligible", () => {
  const r = policy(
    lowEnvelopeWrite({ reversibility: Reversibility.Irreversible }),
    EARNED_DIAL,
  );
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("not-reversible:no-auto"));
});

test("prod writes always gate", () => {
  const r = policy(lowEnvelopeWrite({ environment: Environment.Prod }), EARNED_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("prod-or-unknown-env:no-auto"));
});

test("unknown environment is treated as prod-equivalent (fail safe)", () => {
  const r = policy(lowEnvelopeWrite({ environment: Environment.Unknown }), EARNED_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
});

test("blast radius beyond the dial removes auto-eligibility", () => {
  const r = policy(lowEnvelopeWrite({ blastRadius: BlastRadius.Wide }), EARNED_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("blast-too-wide:no-auto"));
});

test("no rollback on a write => no autonomy, ever", () => {
  const r = policy(lowEnvelopeWrite({ hasRollback: false }), EARNED_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("no-rollback:no-auto"));
});

test("context raises caution, never permission: a caution blocks auto", () => {
  const r = policy(lowEnvelopeWrite({ contextCautions: 1 }), EARNED_DIAL);
  assert.equal(r.decision, Decision.RouteToOwner);
  assert.ok(r.reasons.includes("context-caution:no-auto"));
});

test("unresolved owner => escalate (never a silent auto-route)", () => {
  const r = policy(lowEnvelopeWrite({ ownerResolved: false }), EARNED_DIAL);
  assert.equal(r.decision, Decision.Escalate);
  assert.ok(r.reasons.includes("owner-unresolved:escalate"));
});

test("low-confidence ownership => escalate, not auto-route", () => {
  const r = policy(lowEnvelopeWrite({ ownerConfidence: Confidence.Low }), EARNED_DIAL);
  assert.equal(r.decision, Decision.Escalate);
});

test("audit divergence is itself an escalation trigger", () => {
  const r = policy(lowEnvelopeWrite({ auditDivergence: true }), EARNED_DIAL);
  assert.equal(r.decision, Decision.Escalate);
  assert.ok(r.reasons.includes("audit-divergence:escalate"));
});

test("unknown action fails safe to escalation (catalog is the boundary)", () => {
  const r = policy(lowEnvelopeWrite({ actionCatalogued: false }), EARNED_DIAL);
  assert.equal(r.decision, Decision.Escalate);
  assert.ok(r.reasons.includes("unknown-action:fail-safe"));
});

test("fail-safe ordering: divergence dominates an otherwise-perfect envelope", () => {
  const r = policy(
    lowEnvelopeWrite({ auditDivergence: true }),
    EARNED_DIAL,
  );
  assert.equal(r.decision, Decision.Escalate);
});

test("policy is a pure function: same input => same output", () => {
  const input = lowEnvelopeWrite();
  const a = policy(input, EARNED_DIAL);
  const b = policy(input, EARNED_DIAL);
  assert.deepEqual(a, b);
});
