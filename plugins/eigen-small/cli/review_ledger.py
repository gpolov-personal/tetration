"""Cross-phase review ledger for eigen-small.

A persisted registry of per-phase human review approvals produced by the
`small_review` command: for each phase, whether a human has walked its specs +
goals and confirmed them well-conceived and AC-complete. `small_build
--unsupervised` reads this to gate the sequential multi-phase run — it only
fires when **every discovered phase** is `approved`.

Like the freeze ledger, this is a **thin JSON** over eigen-core atomic I/O,
deliberately separate from the single-phase `pipeline_state_small.json` (which
owns one phase slot per run). Approvals are cross-phase by nature and are
discovered by disk, so they live in their own ledger — not in the flat state.
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

REVIEW_LEDGER_RELATIVE_PATH = "eigen_initiative/phases/review_ledger.json"
SCHEMA = "eigen-small-review/1"
VALID_REVIEW_STATUS = {"pending", "approved"}


@dataclass
class Review:
    phase: int = 1
    status: str = "pending"  # pending | approved
    note: str | None = None
    reviewed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "status": self.status,
            "note": self.note,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Review":
        return cls(
            phase=int(d.get("phase", 1)),
            status=d.get("status", "pending"),
            note=d.get("note"),
            reviewed_at=d.get("reviewed_at"),
        )


@dataclass
class ReviewLedger:
    schema: str = SCHEMA
    reviews: list = field(default_factory=list)
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "reviews": [r.to_dict() for r in self.reviews],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewLedger":
        return cls(
            schema=d.get("schema", SCHEMA),
            reviews=[Review.from_dict(r) for r in (d.get("reviews") or [])],
            updated_at=d.get("updated_at"),
        )


def resolve_ledger_file(eigen_root: str | Path) -> Path:
    return _resolve(eigen_root, REVIEW_LEDGER_RELATIVE_PATH)


def load_ledger(ledger_file: str | Path) -> ReviewLedger:
    """Load the review ledger, or an empty one if the file does not exist yet.

    Propagates ``CorruptStateFile`` (malformed JSON) — never silently re-init.
    """
    raw = load_raw_state(ledger_file)
    if raw is None:
        return ReviewLedger()
    return ReviewLedger.from_dict(raw)


def save_ledger(ledger: ReviewLedger, ledger_file: str | Path) -> None:
    """Atomic save via eigen-core (sets updated_at inside save_raw_state)."""
    save_raw_state(ledger.to_dict(), ledger_file)


def set_review(ledger: ReviewLedger, review: Review) -> ReviewLedger:
    """Record a phase's review status (idempotent on phase — re-recording replaces)."""
    review.reviewed_at = datetime.now(timezone.utc).isoformat()
    ledger.reviews = [r for r in ledger.reviews if r.phase != review.phase]
    ledger.reviews.append(review)
    return ledger


def all_approved(ledger: ReviewLedger, phases: list[int]) -> bool:
    """True iff every phase in ``phases`` has an ``approved`` entry.

    The gate for `small_build --unsupervised`: it discovers the phases on disk
    and asks whether the human approved them all before any unattended build.
    An empty ``phases`` list is treated as not-approved (nothing to run).
    """
    if not phases:
        return False
    by_phase = {r.phase: r.status for r in ledger.reviews}
    return all(by_phase.get(p) == "approved" for p in phases)


__all__ = [
    "REVIEW_LEDGER_RELATIVE_PATH",
    "SCHEMA",
    "VALID_REVIEW_STATUS",
    "Review",
    "ReviewLedger",
    "resolve_ledger_file",
    "load_ledger",
    "save_ledger",
    "set_review",
    "all_approved",
]
