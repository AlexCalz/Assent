# Vision

## Mission

Make autonomous security defense **trustworthy enough to act.** Assent is the control
plane that lets AI agents take real, high-stakes action on infrastructure — with
context-grounded reasoning, ownership-aware approval, and risk-tiered autonomy — so
that "the agent fixed it" is something a security team can actually allow.

## The problem

Almost all agentic security tooling today is either **offensive** (pentest/exploit
agents) or **read-only** (triage, investigation, summarization). Nobody has shipped
autonomous *defense with write access*, and the reason isn't the agents — it's trust.
The blockers are well known:

- Incorrect or harmful auto-fixes
- Over-privileged agentic systems
- Auditing / lack of accountability
- False positives
- Duplication with existing tools
- Poisoned inputs (logs, docs, tickets treated as instructions)
- Misconfiguration
- Over-reliance on automation

Every one of these is a *trust* problem. Solve trust and autonomous remediation becomes
possible. That is the whole thesis.

## The wedge

Not "agents that do security work" — that space (autonomous triage / AI SOC analysts)
is crowded and read-only. The wedge is the **control layer those tools are missing**:

> **Context-grounded, ownership-aware, risk-tiered gating of agent actions.**

The agents are the demo. The gating engine is the company.

### Positioning

- **AI-SOC / triage startups** (Dropzone, Prophet, Charlotte AI, Simbian, Qevlar…):
  investigate & recommend, human executes. Stay read-only to sidestep the trust
  problem. → We are the remediation-and-control layer they lack. *Potential partners,
  not just competitors.*
- **SOAR incumbents** (XSOAR, Splunk SOAR, Tines, Torq): approval gates + audit +
  scoped actions already exist — but as **static playbooks.** → Our edge is *reasoning*
  over novel situations. The demo must show something no playbook anticipated.
- **Agent-governance / identity startups**: building the trust layer as horizontal
  infra. → We build it as a vertical defense product with the agents included.

### The one-liner

> Dropzone tells you what's wrong. Assent is the layer that lets an agent *fix* it
> without blowing up prod.

## The build reframe (validated Aug 2026)

Generic enforcement infrastructure now exists — policy engines, MCP gateways, and
identity-aware runtime guardrails (Palo Alto Prisma AIRS, Microsoft Agent Governance
Toolkit, Silverfort, MCP gateways). **We do not build the enforcement substrate.** We
*ride on it.*

Assent's product is **computing the gating decision** — the risk envelope, the
authoritative owner, the doc-grounded impact assessment — and handing it to an existing
gateway to enforce. The moat is *deciding what the policy should be,* not enforcing it.
This turns three would-be competitors into substrate and slashes the build.

See [competitive-landscape.md](competitive-landscape.md) for the full read.

## Open risks to the wedge (must validate)

1. **Feature vs. product:** could triage incumbents bolt on a remediation module and
   make us a checkbox? Our defense: the gating engine + independent audit agent +
   cross-tool privilege model is genuinely hard and separable.
2. **Will anyone grant write access — ever?** Existential. Validate CISO appetite
   *before* building: *"Under what exact conditions, if any, would you let an agent
   change production without a human clicking execute?"*
3. **Why now?** LLMs can reason about novel situations vs. pre-written playbooks. The
   demo must prove it.
