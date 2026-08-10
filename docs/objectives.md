# Objectives & Design Principles

## Objectives

1. **Ship autonomous value on day one — with zero write risk.** Read-only posture
   visibility and Q&A ("what are we vulnerable to right now?") earns trust before we
   ever touch anything.
2. **Make the approval card the best in the industry.** Fast, clear, complete: exact
   command, target, blast radius, reasoning, and rollback. This is the hero component.
3. **Prove risk-tiered autonomy.** Auto-execute low-risk-to-act changes; gate the rest.
   The dial is *earned per customer,* not a launch default.
4. **Route approvals to the real owner of the affected stack** — not a generic SOC
   queue. No bottlenecks, no rubber-stamping.
5. **Ground agents in the customer's own operational context** (runbooks, arch docs,
   postmortems), not just threat intel — so risk assessments are real.
6. **Independent audit agent as a first-class safety property**, not a log viewer.

## The core primitive

Everything reduces to one object + one engine.

```
Change {
  action:        exact command + target
  reasoning:     why — grounded in internal docs
  risk_envelope: blast_radius × reversibility × environment × confidence
  owner:         who is authoritative for this stack
  rollback:      the undo plan
}

PolicyEngine( risk_envelope, owner ) -> { auto-execute | route-to-owner | escalate }
```

## Non-negotiable principles

- **Gate on risk-to-act, not threat severity.** A reversible, narrow, non-prod change
  is low-envelope even during a critical incident. Key on
  `blast_radius × reversibility × environment × confidence`.
- **Keep the LLM out of the trust decision.** The model *proposes*; a deterministic
  policy engine computes the envelope and decides the gate. Reversibility/blast radius
  come from action type + target, not the model's opinion.
- **Reads are autonomous, writes always gate** (until the dial is earned). The real
  trust boundary is read vs. write, not just environment.
- **Every write has a rollback.** No undo plan → no autonomy, ever.
- **Context raises caution, never grants permission.** Internal docs inform the risk
  score but can never lower a gate below its policy floor. (Poisoned-doc defense.)
- **Untrusted data is never an instruction.** Logs, tickets, doc contents cannot be
  interpreted as commands. NL commands produce a *plan*, never a direct execution.
- **Incomplete data degrades to "ask a human," never "guess and act."** Missing owner
  or low confidence → escalate/broaden. Gaps cost latency, not safety.
- **The audit agent is independent.** A second opinion on the risk envelope from a
  system with no stake in the action. Acting-vs-audit disagreement is itself an
  escalation trigger.
