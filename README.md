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

## Code

The deterministic moat is now a reference implementation — the `Change` primitive and
the pure-function `PolicyEngine`, exactly the part `docs/policy-engine.md` says "must be
code: auditable, testable, versioned." No LLM calls, no third-party dependencies.

| Path | Purpose |
|---|---|
| [assent/change.py](assent/change.py) | The `Change` primitive + risk-envelope types |
| [assent/catalog.py](assent/catalog.py) | The action catalog — the safety boundary (reversibility per action type) |
| [assent/policy.py](assent/policy.py) | The deterministic `PolicyEngine`: `(risk_envelope, owner) -> {auto \| route \| escalate}` |
| [tests/test_policy.py](tests/test_policy.py) | Invariant tests — each pins a principle from the docs |
| [examples/demo.py](examples/demo.py) | Four scenarios showing the three gates and *why* |

```bash
pytest                     # run the invariant suite
python examples/demo.py    # watch the engine gate four changes
```

Status: **concept validated; deterministic core prototyped.** The policy engine is real,
tested code. The LLM-facing pieces (diagnosis, catalog normalization, ownership-graph
population, audit agent) are still design, not build.
