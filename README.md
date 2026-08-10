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

## The kernel

The docs designate one thing as the moat: the deterministic `Change` primitive plus the
pure `policy()` trust decision — *"must be code: auditable, testable, versioned"*
(D2, D6). That core now exists as a small, zero-dependency TypeScript reference kernel.

| File | Role |
|---|---|
| [src/types.ts](src/types.ts) | The `Change` primitive + envelope types; the type boundary *is* the trust boundary |
| [src/catalog.ts](src/catalog.ts) | Action catalog — pre-classified reversibility/effect; the safety boundary |
| [src/policy.ts](src/policy.ts) | The pure `policy()` function — the trust decision, encoding the D6 invariant |
| [src/engine.ts](src/engine.ts) | Wires proposal → normalize → envelope → owner → policy, with independent-audit divergence |
| [test/](test) | 29 tests, each defending one documented invariant (incl. the anti-"99%-confidence" case) |

```
npm test        # runs the suite (Node ≥22.6, TypeScript run directly, no build step)
npm run typecheck
```

Diagnosis (LLM) sits upstream and enforcement (an existing gateway, per D5) sits
downstream. Only the part that *must* be deterministic — computing the decision — lives
here.

Status: **concept + reference kernel.** The strategy is captured in `docs/`; the trust
decision is now executable and tested.
