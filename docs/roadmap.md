# Roadmap — Plan of Action

Autonomy is a dial you *earn*, not a launch feature. Sequence to earn trust.

## Phase 0 — Validate the wedge (before any code)
The wedge is a **customer-appetite bet, not a technical one.**
- [ ] 5–10 conversations with SOC leads / CISOs on the one question:
      *"Under what exact conditions — if any — would you let an AI agent change
      production without a human clicking execute?"*
- [ ] Confirm remediation white space is still open (web-check current state of
      Dropzone / Prophet / Charlotte / agent-governance players).
- [ ] Decide: is "safe autonomous remediation" a standalone product or a feature?

## Phase 1 — Read-only co-pilot (zero write risk)
- [ ] Infra **Overview** page: diagram of what the system sees (firewall, routers,
      Kubernetes, servers…).
- [ ] **Chat** that answers posture questions from real data ("is Cortex installed on
      X?", "what are we vulnerable to right now?").
- [ ] Audit log of everything the system observes.
- **Goal:** immediately useful, touches nothing dangerous, earns trust.

## Phase 2 — Suggest-only (approval UX gets battle-tested)
- [ ] Agents work **Tickets** and *propose* actions via the approval card (exact
      command, target, blast radius, reasoning, rollback).
- [ ] Human executes. NL "text-to-action" produces a *plan*, never a direct execution.
- [ ] Agent **org chart** view (SOC analyst → SOC / mgr / audit agents → CISO level).
- **Goal:** prove the approval card + the Change primitive.

## Phase 3 — Bounded autonomy (earn the dial)
- [x] Policy engine: `(risk_envelope, owner) -> {auto | route | escalate}`. → `assent/policy.py` (D7).
- [x] Ownership + context graph (see [graph-strategy.md](graph-strategy.md)),
      lazy/JIT population. → `assent/graph.py` (D8).
- [x] Independent **audit agent** as second opinion on the risk envelope; disagreement
      → escalation. → `assent/audit.py` + engine integration (D9).
- [ ] Auto-execute low-envelope writes in non-prod, SIEM-watched, one-click rollback.
      *(needs real enforcement substrate + a live environment — not yet built.)*
- **Goal:** the differentiated core — context-grounded, ownership-aware, risk-tiered
  gating.

## Next-to-explore queue
Ideas to pull into a design session when we get there:

- [x] **Policy engine design** — how the risk envelope is computed; where the
      deterministic / LLM boundary sits. → Prototyped as code in `assent/` (see D7):
      the `Change` primitive, the action catalog as the safety boundary, and the
      deterministic `policy()` pure function, with an invariant test suite.
- [x] **Approval card design** — the hero component; make approval fast + complete.
      → Built as `assent/approval_card.py` (see D8): renders a gated `Change` + the
      engine's audit trail from real `PolicyResult` output. `examples/render_cards.py`
      produces the approval-queue page end-to-end (graph → engine → card).
- [ ] **Demo narrative** — the single "wow" flow: an agent handling something no
      playbook anticipated.
- [ ] **Technical architecture** — agent orchestration, JIT/privilege model, policy
      engine, audit pipeline.
- [ ] **Liability / accountability model** — who's responsible when an agent acts.
- [ ] **Data source-of-truth** — integrate vs. discover for the Overview map.
