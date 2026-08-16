# Assent

A control plane for **safe agentic security defense** — the layer that lets AI agents
take real action on infrastructure without blowing up production.

> Incumbent AI-SOC tools tell you what's wrong. Assent is the layer that lets an agent
> *fix* it — with context-grounded, ownership-aware, risk-tiered gating.

The name says the product: nothing acts without **assent** — either an earned policy
assent (low-risk, auto) or a human owner's assent (everything else).

## Run it

```bash
python -m assent.app        # then open http://127.0.0.1:8000
```

Mission control with:

- **Agent roster** — proposer, ownership resolver, independent auditor, policy engine
- **Incident packages** — executive summary, MITRE context, timeline, IOCs, agent traces
- **Gated remediation** — Assent's approval card (risk envelope + owner + rollback)
- **Overview** — inventory map (`/overview`)
- **Tamper-evident ledger** — `/ledger`
- **Demo inject** — one-click multi-signal scenario
- **Dual profiles** — Cloud Personal/Startup or Private Tenant/Agency

Surfaces inspired by TRIDENT-AI's ops IA; every gate decision still comes from Assent's
deterministic engine (confidence never authorizes). Standard library only.

## Docs

| Doc | Purpose |
|---|---|
| [docs/vision.md](docs/vision.md) | Mission, the problem, the wedge, positioning vs. incumbents |
| [docs/objectives.md](docs/objectives.md) | Objectives + non-negotiable design principles |
| [docs/policy-engine.md](docs/policy-engine.md) | The gating engine — where the deterministic/LLM boundary sits |
| [docs/graph-strategy.md](docs/graph-strategy.md) | Populating the ownership + context graph without a 6-month slog |
| [docs/competitive-landscape.md](docs/competitive-landscape.md) | Market read (Aug 2026) + the "ride on enforcement" reframe |
| [docs/roadmap.md](docs/roadmap.md) | Plan of action (crawl → walk → run) + the "next to explore" queue |
| [docs/decisions.md](docs/decisions.md) | Running log of key decisions and *why* (see **D11**) |

## Code

| Path | Purpose |
|---|---|
| [assent/runtime.py](assent/runtime.py) | Orchestrator — signal → propose → owner → audit → gate → act/queue |
| [assent/app.py](assent/app.py) | HTTP entry — demo world, demo inject, profile switcher |
| [assent/dashboard.py](assent/dashboard.py) | Mission control UI (Trident IA, Assent brand) |
| [assent/package.py](assent/package.py) | Incident package projection over a gated `Change` |
| [assent/agents.py](assent/agents.py) | Live agent roster derived from runtime state |
| [assent/policy.py](assent/policy.py) | Deterministic `PolicyEngine` |
| [assent/approval_card.py](assent/approval_card.py) | Hero approval / remediation card |
| [assent/graph.py](assent/graph.py) | Ownership graph |
| [assent/audit.py](assent/audit.py) | Independent audit agent |
| [assent/ledger.py](assent/ledger.py) | Hash-chained audit trail |

```bash
pytest                           # invariant + dashboard suite
python -m assent.app             # control plane
python examples/demo.py          # watch the engine gate changes
```

Status: **working prototype** with Trident-inspired mission control on top of the
deterministic gating core. LLM diagnosis and real enforcement adapters remain next.
