"""Incident package — Trident's crown-jewel view, remapped for Assent.

TRIDENT-AI synthesizes an IncidentPackage (exec summary, MITRE, timeline, IOCs,
blast radius, remediation options, agent trace) for analyst HITL. Assent keeps that
*presentation* shape but grounds every gate-relevant fact in measured data:

* blast radius / environment / reversibility come from the Change envelope
* owner comes from the ownership graph
* remediation is a single gated Change (not a free-form MCP option list)
* confidence is displayed but never authorizes (D6)

Packages are pure views over ``ChangeRecord`` — they cannot relax the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from assent.change import Change
from assent.policy import Decision
from assent.proposer import Signal
from assent.runtime import ChangeRecord, ChangeState


# Optional MITRE hints keyed by signal kind — enrich the package, never the gate.
_MITRE_BY_KIND: Mapping[str, List[Dict[str, str]]] = {
    "malicious_domain": [
        {"id": "T1071", "name": "Application Layer Protocol", "tactic": "Command and Control"},
        {"id": "T1048", "name": "Exfiltration Over Alternative Protocol", "tactic": "Exfiltration"},
    ],
    "c2_beacon": [
        {"id": "T1071", "name": "Application Layer Protocol", "tactic": "Command and Control"},
        {"id": "T1573", "name": "Encrypted Channel", "tactic": "Command and Control"},
    ],
    "leaked_credential": [
        {"id": "T1552", "name": "Unsecured Credentials", "tactic": "Credential Access"},
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Initial Access"},
    ],
    "overprivileged_role": [
        {"id": "T1098", "name": "Account Manipulation", "tactic": "Persistence"},
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Privilege Escalation"},
    ],
    "compromised_session": [
        {"id": "T1539", "name": "Steal Web Session Cookie", "tactic": "Credential Access"},
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Initial Access"},
    ],
    "ransomware_precursor": [
        {"id": "T1490", "name": "Inhibit System Recovery", "tactic": "Impact"},
        {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "Impact"},
    ],
}


@dataclass(frozen=True)
class MitreTechnique:
    id: str
    name: str
    tactic: str


@dataclass(frozen=True)
class TimelineEvent:
    timestamp: str
    event: str
    source: str  # sensor | proposer | auditor | policy | human


@dataclass(frozen=True)
class AgentTrace:
    proposer: Dict[str, Any] = field(default_factory=dict)
    ownership: Dict[str, Any] = field(default_factory=dict)
    auditor: Dict[str, Any] = field(default_factory=dict)
    policy: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IncidentPackage:
    """Assent's incident package — Trident-shaped, Assent-grounded."""

    record_id: str
    title: str
    status: str
    decision: str
    severity: str  # threat severity from the signal (display only)
    executive_summary: str
    technical_summary: str
    root_cause: str
    contributing_factors: List[str]
    attack_timeline: List[TimelineEvent]
    mitre_techniques: List[MitreTechnique]
    iocs: Dict[str, List[str]]
    affected_services: List[str]
    blast_radius_narrative: str
    business_impact: str
    confidence: float
    owner: str
    environment: str
    reversibility: str
    rollback: str
    agent_trace: AgentTrace
    gate_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "title": self.title,
            "status": self.status,
            "decision": self.decision,
            "severity": self.severity,
            "executive_summary": self.executive_summary,
            "technical_summary": self.technical_summary,
            "root_cause": self.root_cause,
            "contributing_factors": list(self.contributing_factors),
            "attack_timeline": [
                {"timestamp": e.timestamp, "event": e.event, "source": e.source}
                for e in self.attack_timeline
            ],
            "mitre_techniques": [
                {"id": m.id, "name": m.name, "tactic": m.tactic}
                for m in self.mitre_techniques
            ],
            "iocs": {k: list(v) for k, v in self.iocs.items()},
            "affected_services": list(self.affected_services),
            "blast_radius_narrative": self.blast_radius_narrative,
            "business_impact": self.business_impact,
            "confidence": self.confidence,
            "owner": self.owner,
            "environment": self.environment,
            "reversibility": self.reversibility,
            "rollback": self.rollback,
            "agent_trace": {
                "proposer": dict(self.agent_trace.proposer),
                "ownership": dict(self.agent_trace.ownership),
                "auditor": dict(self.agent_trace.auditor),
                "policy": dict(self.agent_trace.policy),
            },
            "gate_reasons": list(self.gate_reasons),
        }


def build_package(record: ChangeRecord) -> IncidentPackage:
    """Project a ChangeRecord into an incident package for the dashboard."""
    signal = record.signal
    change = record.change
    decision = record.decision.value if record.decision else "triage"
    when = record.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

    mitre = [
        MitreTechnique(**m) for m in _MITRE_BY_KIND.get(signal.kind, [])
    ]
    iocs = _iocs_from_indicators(signal.indicators)
    factors = _contributing_factors(signal, change)

    if change is None:
        return IncidentPackage(
            record_id=record.id,
            title=f"{signal.kind} → {signal.target}",
            status=record.state.value,
            decision="triage",
            severity=signal.severity,
            executive_summary=(
                f"A {signal.severity} signal ({signal.kind}) arrived for "
                f"{signal.target}, but Assent has no playbook that maps it to a "
                f"catalogued action. Incomplete data degrades to ask-a-human."
            ),
            technical_summary=signal.summary or "No technical summary supplied.",
            root_cause=f"Unmapped signal kind '{signal.kind}'.",
            contributing_factors=factors,
            attack_timeline=[
                TimelineEvent(when, f"Signal {signal.kind} from {signal.source}", "sensor"),
                TimelineEvent(when, "Proposer refused — no catalogued action", "proposer"),
            ],
            mitre_techniques=mitre,
            iocs=iocs,
            affected_services=[signal.target],
            blast_radius_narrative="Unknown — no action proposed; assume worst until mapped.",
            business_impact=_business_impact(signal.severity, None),
            confidence=0.0,
            owner="unresolved",
            environment="unknown",
            reversibility="unknown",
            rollback="—",
            agent_trace=AgentTrace(
                proposer={"refused": True, "reason": record.reasons[0] if record.reasons else ""},
                ownership={},
                auditor={},
                policy={"decision": "needs_triage"},
            ),
            gate_reasons=list(record.reasons),
        )

    env = change.risk_envelope
    owner = change.owner.id if change.owner.known else "unresolved"
    blast_n = (
        f"{env.blast_radius} system"
        + ("" if env.blast_radius == 1 else "s")
        + (" · tier-0" if env.hits_tier0 else "")
    )

    exec_summary = (
        f"Assent proposes {change.action.type} on {change.action.target} "
        f"({env.environment.value}). Gate decision: {_decision_plain(record)}. "
        f"Owner: {owner}. Confidence is {round(env.confidence * 100)}% — "
        f"confidence never authorizes; only a low risk envelope can auto-assent."
    )
    tech = change.reasoning or signal.summary or "Proposal derived from playbook."
    timeline = [
        TimelineEvent(when, f"Signal {signal.kind} from {signal.source}", "sensor"),
        TimelineEvent(
            when,
            f"Proposer → {change.action.type} (confidence {round(env.confidence * 100)}%)",
            "proposer",
        ),
        TimelineEvent(
            when,
            f"Owner resolved: {owner} ({change.owner.source}, "
            f"{round(change.owner.confidence * 100)}%)"
            if change.owner.known
            else "Owner unresolved — will escalate",
            "ownership",
        ),
    ]
    if record.audit is not None:
        audit = record.audit
        stance = "dissents" if audit.dissent else "second opinion"
        timeline.append(
            TimelineEvent(
                when,
                f"Auditor {stance} at {round(audit.confidence * 100)}%: {audit.rationale or '—'}",
                "auditor",
            )
        )
    timeline.append(
        TimelineEvent(
            when,
            f"Policy → {decision}: {record.reasons[0] if record.reasons else '—'}",
            "policy",
        )
    )

    return IncidentPackage(
        record_id=record.id,
        title=f"{change.action.type} → {change.action.target}",
        status=record.state.value,
        decision=decision,
        severity=signal.severity,
        executive_summary=exec_summary,
        technical_summary=tech,
        root_cause=signal.summary or change.reasoning or signal.kind,
        contributing_factors=factors,
        attack_timeline=timeline,
        mitre_techniques=mitre,
        iocs=iocs,
        affected_services=[change.action.target],
        blast_radius_narrative=blast_n,
        business_impact=_business_impact(signal.severity, env.environment.value),
        confidence=env.confidence,
        owner=owner,
        environment=env.environment.value,
        reversibility=env.reversibility.value,
        rollback=change.rollback or "no rollback plan — autonomy withheld",
        agent_trace=AgentTrace(
            proposer={
                "action": change.action.type,
                "target": change.action.target,
                "params": dict(change.action.params),
                "confidence": env.confidence,
                "reasoning": change.reasoning,
            },
            ownership={
                "owner": change.owner.id,
                "source": change.owner.source,
                "confidence": change.owner.confidence,
                "known": change.owner.known,
            },
            auditor=(
                {
                    "confidence": record.audit.confidence,
                    "dissent": record.audit.dissent,
                    "rationale": record.audit.rationale,
                }
                if record.audit
                else {}
            ),
            policy={
                "decision": decision,
                "reasons": list(record.reasons),
                "state": record.state.value,
                "blast_radius": env.blast_radius,
                "reversibility": env.reversibility.value,
                "environment": env.environment.value,
                "hits_tier0": env.hits_tier0,
            },
        ),
        gate_reasons=list(record.reasons),
    )


def _decision_plain(record: ChangeRecord) -> str:
    if record.decision is Decision.AUTO:
        return "auto-executed (low risk envelope)"
    if record.decision is Decision.ROUTE_TO_OWNER:
        return "routed to owner for assent"
    if record.decision is Decision.ESCALATE:
        return "escalated"
    if record.state is ChangeState.NEEDS_TRIAGE:
        return "needs triage"
    return record.state.value


def _iocs_from_indicators(indicators: Mapping[str, str]) -> Dict[str, List[str]]:
    ips: List[str] = []
    domains: List[str] = []
    users: List[str] = []
    other: List[str] = []
    for key, value in indicators.items():
        low = key.lower()
        if "ip" in low:
            ips.append(value)
        elif "domain" in low or "host" in low:
            domains.append(value)
        elif "user" in low or "account" in low:
            users.append(value)
        else:
            other.append(f"{key}={value}")
    return {"ips": ips, "domains": domains, "users": users, "other": other}


def _contributing_factors(signal: Signal, change: Optional[Change]) -> List[str]:
    factors = [f"Reported by {signal.source}", f"Threat severity {signal.severity}"]
    if change is not None:
        env = change.risk_envelope
        factors.append(f"Environment measured as {env.environment.value}")
        factors.append(f"Reversibility classified as {env.reversibility.value}")
        if env.hits_tier0:
            factors.append("Target is tier-0 / crown-jewel")
    return factors


def _business_impact(severity: str, environment: Optional[str]) -> str:
    """Display-only narrative. Never feeds the gate."""
    if environment == "prod" and severity in {"critical", "high"}:
        return "High — production path; contain before lateral movement."
    if environment in {"staging", "dev"}:
        return "Contained — non-prod; safe for low-envelope autonomy when earned."
    if severity == "critical":
        return "Elevated — critical threat severity (display only; gate uses risk-to-act)."
    return "Moderate — review owner routing and rollback before assent."
