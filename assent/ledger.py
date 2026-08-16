"""The audit ledger — tamper-evident accountability.

``docs/vision.md`` lists "auditing / lack of accountability" as one of the trust
blockers that keeps agents read-only. A log an operator can quietly edit doesn't answer
that. This ledger is append-only and **hash-chained**: every entry commits to the hash
of the one before it, so removing or altering any historical entry breaks the chain and
``verify()`` reports exactly where.

Every consequential moment goes here — the proposal, the decision and its reasons, the
audit opinion, the execution, the human approval or denial, the rollback — so "who
allowed this, and on what basis" is answerable after the fact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


GENESIS = "0" * 64


@dataclass(frozen=True)
class LedgerEntry:
    """One immutable record in the chain."""

    seq: int
    at: datetime
    kind: str                 # proposed | decided | executed | approved | denied | rolled_back | failed
    change_id: str
    actor: str                # "assent" for machine steps, a person/team id for human ones
    detail: Dict[str, Any]
    prev_hash: str
    entry_hash: str

    def payload(self) -> Dict[str, Any]:
        """The canonical, hashed content of this entry (everything but its own hash)."""
        return {
            "seq": self.seq,
            "at": self.at.isoformat(),
            "kind": self.kind,
            "change_id": self.change_id,
            "actor": self.actor,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
        }


def _hash_payload(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Ledger:
    """Append-only, hash-chained audit log."""

    _entries: List[LedgerEntry] = field(default_factory=list)

    def append(
        self,
        kind: str,
        change_id: str,
        detail: Optional[Dict[str, Any]] = None,
        actor: str = "assent",
        at: Optional[datetime] = None,
    ) -> LedgerEntry:
        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS
        payload = {
            "seq": len(self._entries) + 1,
            "at": (at or datetime.now(timezone.utc)).isoformat(),
            "kind": kind,
            "change_id": change_id,
            "actor": actor,
            "detail": detail or {},
            "prev_hash": prev_hash,
        }
        entry = LedgerEntry(
            seq=payload["seq"],
            at=datetime.fromisoformat(payload["at"]),
            kind=kind,
            change_id=change_id,
            actor=actor,
            detail=payload["detail"],
            prev_hash=prev_hash,
            entry_hash=_hash_payload(payload),
        )
        self._entries.append(entry)
        return entry

    def entries(self, change_id: Optional[str] = None) -> List[LedgerEntry]:
        if change_id is None:
            return list(self._entries)
        return [e for e in self._entries if e.change_id == change_id]

    def verify(self) -> tuple[bool, str]:
        """Recompute the chain. Returns ``(ok, message)``; on failure the message names
        the first entry that doesn't reconcile."""
        prev = GENESIS
        for entry in self._entries:
            if entry.prev_hash != prev:
                return False, f"entry {entry.seq} does not link to entry {entry.seq - 1}"
            if _hash_payload(entry.payload()) != entry.entry_hash:
                return False, f"entry {entry.seq} content does not match its hash"
            prev = entry.entry_hash
        return True, f"chain intact across {len(self._entries)} entries"

    def __len__(self) -> int:
        return len(self._entries)
