# Assent

A control plane for **safe agentic security defense** — the layer that lets AI agents
take real action on infrastructure without blowing up production.

> Incumbent AI-SOC tools tell you what's wrong. Assent is the layer that lets an agent
> *fix* it — with context-grounded, ownership-aware, risk-tiered gating.

The name says the product: nothing acts without **assent** — either an earned policy
assent (low-risk, auto) or a human owner's assent (everything else).

## What's here

| Doc | Purpose |
|---|---|
| [docs/vision.md](docs/vision.md) | Mission, the problem, the wedge, positioning vs. incumbents |
| [docs/objectives.md](docs/objectives.md) | Objectives + non-negotiable design principles |
| [docs/policy-engine.md](docs/policy-engine.md) | The gating engine — where the deterministic/LLM boundary sits |
| [docs/graph-strategy.md](docs/graph-strategy.md) | Populating the ownership + context graph without a 6-month slog |
| [docs/competitive-landscape.md](docs/competitive-landscape.md) | Market read (Aug 2026) + the "ride on enforcement" reframe |
| [docs/roadmap.md](docs/roadmap.md) | Plan of action (crawl → walk → run) + the "next to explore" queue |
| [docs/decisions.md](docs/decisions.md) | Running log of key decisions and *why* |

## Run it

```bash
python -m assent.app        # then open http://127.0.0.1:8000
```

A working control plane: five detections arrive, the engine gates each one, and the
approval queue lets you approve, deny, or undo — with a tamper-evident audit ledger at
`/ledger`. Standard library only; nothing to install.

## Code

The deterministic moat is a reference implementation — the `Change` primitive and
the pure-function `PolicyEngine`, exactly the part `docs/policy-engine.md` says "must be
code: auditable, testable, versioned." No LLM calls, no third-party dependencies.

| Path | Purpose |
|---|---|
| [assent/runtime.py](assent/runtime.py) | The `Assent` orchestrator — signal → propose → resolve owner → audit → gate → act or queue, plus approve/deny/rollback |
| [assent/app.py](assent/app.py) | The web app — approval queue with working controls, and the audit ledger view |
| [assent/change.py](assent/change.py) | The `Change` primitive + risk-envelope types |
| [assent/catalog.py](assent/catalog.py) | The action catalog — the safety boundary (reversibility per action type) |
| [assent/inventory.py](assent/inventory.py) | Measured system facts (environment, blast radius, tier-0). Unknown system → assume the worst |
| [assent/proposer.py](assent/proposer.py) | Signal → typed catalog action. Refuses to propose what the catalog can't classify |
| [assent/executor.py](assent/executor.py) | The hand-off seam to real enforcement (D5), with a simulated adapter for the demo |
| [assent/ledger.py](assent/ledger.py) | Hash-chained, tamper-evident audit trail |
| [assent/policy.py](assent/policy.py) | The deterministic `PolicyEngine`: `(risk_envelope, owner) -> {auto \| route \| escalate}` |
| [assent/graph.py](assent/graph.py) | The ownership graph — "derive, don't demand" resolution (source ladder, confidence-scored edges, staleness decay) |
| [assent/audit.py](assent/audit.py) | The independent audit agent — a second-opinion confidence read; disagreement is a deterministic escalation |
| [assent/approval_card.py](assent/approval_card.py) | The approval card — renders a gated `Change`, the second opinion, and the audit trail as the human decision surface |
| [tests/](tests/) | Invariant tests — each pins a principle from the docs |
| [examples/demo.py](examples/demo.py) | Four scenarios showing the three gates and *why* |
| [examples/render_cards.py](examples/render_cards.py) | End-to-end slice: graph resolves owner → engine gates → card renders |

```bash
pytest                           # run the invariant suite (75 tests)
python -m assent.app             # run the control plane
python examples/demo.py          # watch the engine gate four changes
python examples/render_cards.py  # generate a static approval-queue page
```

Status: **working prototype.** The full loop runs end to end — detection in, gated
decision out, human approval or auto-execution, undo, and a verifiable audit trail —
backed by 75 tests. The remaining pieces are the LLM-facing diagnosis layer (today a
deterministic playbook stands in) and real enforcement adapters (today simulated).
