"""Execution — the boundary where Assent hands off to real enforcement.

Decision **D5**: we don't build the enforcement substrate. Gateways and policy
enforcement points already exist (Prisma AIRS, MCP gateways, the Microsoft agent
governance toolkit); Assent computes the gating *decision* and hands the approved
action to one of them. This module is that seam.

``Executor`` is the protocol a real adapter implements. ``SimulatedExecutor`` is the
in-memory stand-in used by the demo app and the tests: it records what *would* have run
and supports undo, so the whole product is exercisable without touching infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, runtime_checkable

from assent.change import Change


@dataclass(frozen=True)
class ExecutionResult:
    """What happened when the action was handed to the enforcement layer."""

    ok: bool
    detail: str
    handle: str = ""   # opaque reference the adapter can use to undo


@runtime_checkable
class Executor(Protocol):
    def execute(self, change: Change) -> ExecutionResult: ...
    def rollback(self, change: Change, handle: str) -> ExecutionResult: ...


@dataclass
class SimulatedExecutor:
    """Records actions instead of performing them. Safe by construction.

    Refuses to execute a write with no rollback plan — a belt-and-braces echo of the
    engine's rule, so even a caller that bypassed the gate can't strand an unundoable
    change.
    """

    performed: List[str] = field(default_factory=list)
    undone: List[str] = field(default_factory=list)
    _seq: int = 0

    def execute(self, change: Change) -> ExecutionResult:
        if change.action.is_write and not change.has_rollback:
            return ExecutionResult(
                False, "refused: write action carries no rollback plan"
            )
        self._seq += 1
        handle = f"sim-{self._seq}"
        descriptor = f"{change.action.type} -> {change.action.target}"
        self.performed.append(descriptor)
        return ExecutionResult(True, f"executed {descriptor}", handle)

    def rollback(self, change: Change, handle: str) -> ExecutionResult:
        if not change.has_rollback:
            return ExecutionResult(False, "no rollback plan on record")
        descriptor = f"{change.action.type} -> {change.action.target}"
        self.undone.append(descriptor)
        return ExecutionResult(True, f"rolled back {descriptor}", handle)
