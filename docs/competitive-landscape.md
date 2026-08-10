# Competitive Landscape (Aug 2026)

Web-checked to de-risk the wedge. Conclusion: **white space still open, now more
precisely shaped** — *graded, ownership-routed, doc-grounded gating*, not "an AI SOC
analyst" and not "another policy gateway."

## Now table stakes — do NOT position as differentiators

- **Confidence-thresholded autonomy already ships.** Dropzone + Prophet run a
  "double-check" (two agents validate) and auto-isolate a host / reset a password only
  if **confidence > 99%**. Gating on confidence is the current bar, not novel.
- **"Authorize outside the model" is consensus best practice.** Policy engine / tool
  gateway between agent and systems, checked per tool call. Shipped 2026: Microsoft
  Agent Governance Toolkit (Apr), Palo Alto Prisma AIRS 3.0 (Mar), Silverfort
  identity-aware enforcement, MCP gateways. Our principle "keep the LLM out of the trust
  decision" is now industry standard — good validation, but not a differentiator.

## Still unclaimed — the wedge

- **Graded, multi-variable risk-to-act.** Everyone gates on a *single* variable
  (confidence) or a *binary* scope check (may this agent call this tool?). Checked
  BigID's own "agentic remediation" guide — the category leader by name — it says
  "high-impact actions require human approval" but **never defines high-impact, has no
  blast-radius assessment, no ownership routing.** Our `blast_radius × reversibility ×
  environment × confidence` envelope is genuinely absent from the market.
- **Ownership-aware approval routing.** Not found in any vendor. Everyone routes to a
  role/queue, not the authoritative owner of the affected stack.
- **Doc-grounded *operational* risk assessment.** Vendors ground in threat context, not
  the customer's runbooks/arch. The poisoning risk is now openly documented
  ("decisions shaped by tickets, runbooks, chat, logs — the same artifacts an attacker
  can influence"). Our "context raises caution, never permission" rule is the mitigation
  the field is missing.

## Market pull
- **88% of orgs reported an AI-agent security incident in the prior year.** Pain is real
  and current.

## The build reframe
Since enforcement infra exists, **don't build it — ride on it.** Assent computes the
gating *decision* (envelope + owner + doc-grounded assessment) and hands it to an
existing gateway (Prisma / MCP gateway / Microsoft toolkit) to enforce. Three
"competitors" become substrate. Moat = deciding the policy, not enforcing it.

## Sources
- Dropzone AI — https://www.dropzone.ai/ai-soc-analyst
- NomadLab, Best AI SOC Platforms 2026 — https://nomadlab.cc/blog/2026/05/best-ai-soc-platforms-2026-prophet-dropzone-torq-anvilogic-radiant
- TrueFoundry, Enterprise AI Agent Security buyer's guide 2026 — https://www.truefoundry.com/blog/enterprise-ai-agent-security-solutions
- Linx, Top Agentic AI Security Solutions 2026 — https://www.linx.security/blog/top-agentic-ai-security-solutions
- BigID, Agentic Remediation guide — https://bigid.com/blog/agentic-remediation-guide/
- Group-IB, Agentic AI Security — https://www.group-ib.com/resources/knowledge-hub/agentic-ai-security/
- Help Net Security, When your AI assistant has the keys to production — https://www.helpnetsecurity.com/2026/05/20/agentic-ai-security-llm-research/
