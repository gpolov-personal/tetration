"""Cross-phase freeze ledger for eigen-small.

A persisted registry of interface signatures / seams that are **frozen** (immutable
contracts) or deliberately left as extension **hooks** for a future phase (the
SVC-01 no-op-hooks pattern). eigen-small owns marking what carries phase-to-phase:
`small_plan` reads prior phases' entries as read-only inputs (and flags any phase-N
design that would mutate one — a cross-cutting contradiction) and records its own at
close. This is the cross-phase verification a per-phase run otherwise lacks.

Deliberately a **thin JSON** over eigen-core atomic I/O — NOT squared's freeze-ledger
+ dependent-lane-recheck machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from eigen_core.cli.state_io import (
    load_raw_state,
    resolve_state_file as _resolve,
    save_raw_state,
)

FREEZE_LEDGER_RELATIVE_PATH = "eigen_initiative/phases/freeze_ledger.json"
SCHEMA = "eigen-small-freeze/1"
VALID_KINDS = {"frozen", "hook"}  # frozen = immutable contract; hook = extension seam for a later phase


@dataclass
class Seam:
    name: str = ""
    phase: int = 1
    kind: str = "frozen"
    signature: str | None = None
    consumers: list[str] = field(default_factory=list)
    note: str | None = None
    recorded_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "phase": self.phase,
            "kind": self.kind,
            "signature": self.signature,
            "consumers": self.consumers,
            "note": self.note,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Seam":
        return cls(
            name=d.get("name", ""),
            phase=int(d.get("phase", 1)),
            kind=d.get("kind", "frozen"),
            signature=d.get("signature"),
            consumers=list(d.get("consumers") or []),
            note=d.get("note"),
            recorded_at=d.get("recorded_at"),
        )


@dataclass
class FreezeLedger:
    schema: str = SCHEMA
    seams: list = field(default_factory=list)
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "seams": [s.to_dict() for s in self.seams],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FreezeLedger":
        return cls(
            schema=d.get("schema", SCHEMA),
            seams=[Seam.from_dict(s) for s in (d.get("seams") or [])],
            updated_at=d.get("updated_at"),
        )


def resolve_ledger_file(eigen_root: str | Path) -> Path:
    return _resolve(eigen_root, FREEZE_LEDGER_RELATIVE_PATH)


def load_ledger(ledger_file: str | Path) -> FreezeLedger:
    """Load the ledger, or an empty one if the file does not exist yet.

    Propagates ``CorruptStateFile`` (malformed JSON) — never silently re-init.
    """
    raw = load_raw_state(ledger_file)
    if raw is None:
        return FreezeLedger()
    return FreezeLedger.from_dict(raw)


def save_ledger(ledger: FreezeLedger, ledger_file: str | Path) -> None:
    """Atomic save via eigen-core (sets updated_at inside save_raw_state)."""
    save_raw_state(ledger.to_dict(), ledger_file)


def add_seam(ledger: FreezeLedger, seam: Seam) -> FreezeLedger:
    """Append a seam (idempotent on (name, phase) — re-recording replaces)."""
    seam.recorded_at = datetime.now(timezone.utc).isoformat()
    ledger.seams = [
        s for s in ledger.seams if not (s.name == seam.name and s.phase == seam.phase)
    ]
    ledger.seams.append(seam)
    return ledger


__all__ = [
    "FREEZE_LEDGER_RELATIVE_PATH",
    "SCHEMA",
    "VALID_KINDS",
    "Seam",
    "FreezeLedger",
    "resolve_ledger_file",
    "load_ledger",
    "save_ledger",
    "add_seam",
]
