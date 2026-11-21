"""The action catalog — the safety boundary.

Deterministic reversibility and blast-radius classification requires actions to be
*pre-classified*. This is the second design call in ``docs/policy-engine.md``: the
catalog is the safety boundary, and an action the catalog has never been taught fails
safe to human. Coverage is a build cost we accept; auto-executing an unclassified
action is the one thing the engine must never do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from assent.change import Reversibility


@dataclass(frozen=True)
class ActionClass:
    """How a catalogued action type behaves, independent of any single instance.

    ``reversibility`` here is the *ceiling* for the action type; a concrete target may
    be classified more conservatively (e.g. reversible action against a tier-0 system),
    but never less.
    """

    type: str
    is_write: bool
    reversibility: Reversibility
    description: str = ""


class ActionCatalog:
    """A registry of known action types. Unknown type => not classifiable => escalate."""

    def __init__(self, classes: Optional[Dict[str, ActionClass]] = None) -> None:
        self._classes: Dict[str, ActionClass] = dict(classes or {})

    def register(self, action_class: ActionClass) -> "ActionCatalog":
        self._classes[action_class.type] = action_class
        return self

    def get(self, action_type: str) -> Optional[ActionClass]:
        return self._classes.get(action_type)

    def knows(self, action_type: str) -> bool:
        return action_type in self._classes

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._classes))


# A small starter catalog. Real deployments grow this; the point is that reversibility
# is a property of the *action type*, decided once, in code, and reviewable.
DEFAULT_CATALOG = ActionCatalog(
    {
        # --- reads: autonomous, no undo needed ---
        "read_posture": ActionClass(
            "read_posture", is_write=False, reversibility=Reversibility.REVERSIBLE,
            description="Query current security posture / inventory. No state change.",
        ),
        "list_alerts": ActionClass(
            "list_alerts", is_write=False, reversibility=Reversibility.REVERSIBLE,
            description="Read open alerts. No state change.",
        ),
        # --- reversible writes: clean automated undo ---
        "block_domain": ActionClass(
            "block_domain", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Add a domain to the egress blocklist. Undo = remove it.",
        ),
        "disable_user_session": ActionClass(
            "disable_user_session", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Revoke active sessions for a user. Undo = user re-authenticates.",
        ),
        "quarantine_host": ActionClass(
            "quarantine_host", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Network-isolate a host via EDR. Undo = release from isolation.",
        ),
        # --- recoverable writes: undo possible but with cost/latency ---
        "rotate_credential": ActionClass(
            "rotate_credential", is_write=True, reversibility=Reversibility.RECOVERABLE,
            description="Rotate a secret. Consumers must pick up the new value.",
        ),
        "revoke_iam_role": ActionClass(
            "revoke_iam_role", is_write=True, reversibility=Reversibility.RECOVERABLE,
            description="Remove an IAM role binding. Undo = re-grant, may break access.",
        ),
        # --- ARTEX / agentic-attack containment: reversible ---
        "block_webhook_url": ActionClass(
            "block_webhook_url", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Block an exfiltration destination URL at the egress proxy. Undo = unblock.",
        ),
        "revoke_cloud_session": ActionClass(
            "revoke_cloud_session", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Terminate active cloud sessions for an identity. Undo = user re-authenticates.",
        ),
        "freeze_ad_account": ActionClass(
            "freeze_ad_account", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Disable an Active Directory account. Undo = re-enable.",
        ),
        "isolate_cloud_workload": ActionClass(
            "isolate_cloud_workload", is_write=True, reversibility=Reversibility.REVERSIBLE,
            description="Network-isolate a cloud workload (EC2/VM/pod). Undo = restore connectivity.",
        ),
        # --- ARTEX / agentic-attack containment: recoverable ---
        "revoke_app_consent": ActionClass(
            "revoke_app_consent", is_write=True, reversibility=Reversibility.RECOVERABLE,
            description="Remove OAuth/SAML app consent grant. Undo = re-grant, service disruption likely.",
        ),
        "restrict_cloud_role": ActionClass(
            "restrict_cloud_role", is_write=True, reversibility=Reversibility.RECOVERABLE,
            description="Strip elevated cloud role (Global Admin, etc). Undo = re-grant, audit required.",
        ),
        "rotate_app_credential": ActionClass(
            "rotate_app_credential", is_write=True, reversibility=Reversibility.RECOVERABLE,
            description="Rotate an application's client secret/certificate. Downstream apps must update.",
        ),
        "block_lateral_protocol": ActionClass(
            "block_lateral_protocol", is_write=True, reversibility=Reversibility.RECOVERABLE,
            description="Block a lateral-movement protocol (WinRM/PSRemoting/RDP) on a segment. Undo = re-enable.",
        ),
        # --- irreversible writes: never auto, ever ---
        "delete_volume": ActionClass(
            "delete_volume", is_write=True, reversibility=Reversibility.IRREVERSIBLE,
            description="Destroy a storage volume. No undo.",
        ),
        "terminate_instance": ActionClass(
            "terminate_instance", is_write=True, reversibility=Reversibility.IRREVERSIBLE,
            description="Terminate a compute instance. No undo.",
        ),
    }
)
