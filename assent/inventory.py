"""System inventory — the measured facts behind the risk envelope.

``docs/policy-engine.md`` assigns ``environment``, ``blast_radius`` and ``hits_tier0``
to the deterministic side of the line: they can *open* the gate, so they must be
measured, never opined. This module is where those measurements come from.

The critical behavior is the miss case. A system the inventory has never seen is not
assumed safe — it resolves to the **most conservative** possible facts (prod, tier-0,
wide blast radius), which closes the auto gate by construction. Consistent with
"incomplete data degrades to 'ask a human,' never 'guess and act.'"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from assent.change import Environment


@dataclass(frozen=True)
class SystemRecord:
    """Measured facts about one system, sourced from CMDB / cloud tags / K8s / IaC."""

    name: str
    environment: Environment
    tier0: bool = False
    # How many other systems/users are affected when this one is acted on. Drives
    # blast_radius; 0 dependents still means the target itself is affected (radius 1).
    dependents: int = 0

    @property
    def blast_radius(self) -> int:
        return 1 + self.dependents


# The fail-safe record for a system we know nothing about: assume the worst so the
# policy engine cannot auto-execute against it.
def unknown_system(name: str) -> SystemRecord:
    return SystemRecord(
        name=name, environment=Environment.PROD, tier0=True, dependents=99
    )


@dataclass
class Inventory:
    """A registry of measured system facts. Misses fail conservative, never optimistic."""

    _systems: Dict[str, SystemRecord] = field(default_factory=dict)

    def add(self, record: SystemRecord) -> "Inventory":
        self._systems[record.name] = record
        return self

    def knows(self, name: str) -> bool:
        return name in self._systems

    def get(self, name: str) -> SystemRecord:
        """Always returns a record. An unknown system yields the conservative default,
        so callers can't accidentally treat 'unknown' as 'safe'."""
        found = self._systems.get(name)
        return found if found is not None else unknown_system(name)

    def lookup(self, name: str) -> Optional[SystemRecord]:
        """The raw lookup, for callers that need to distinguish a real miss."""
        return self._systems.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._systems))
