"""Typed load/save/validate for eigen-small pipeline state.

A flat, single-phase model:
  - a triage decision: `shape` + two `dials` (structure × rigor),
  - three planning-stage markers (`manifest`/`bootstrap`/`space_split`), each
    recording a reuse/synthesize/skip/done outcome,
  - a `waves` plan (DAG-ordered) with per-epic goal status + per-wave review.

Wraps ``eigen_core.cli.state_io`` (atomic raw JSON I/O). The atomic write is the
whole reason this CLI exists: a markdown command cannot import eigen-core, so the
only way to get tmp-file + os.replace writes (instead of a torn `jq`/`cat >`) is
to shell out to this Python entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eigen_core.cli.state_io import (
    load_raw_state,
    resolve_state_file as _resolve_state_file,
    save_raw_state,
)

SMALL_STATE_RELATIVE_PATH = "eigen_initiative/phases/pipeline_state_small.json"
SCHEMA = "eigen-small/1"

VALID_SHAPES = {"unknown", "direct", "single_phase", "defer_to_squared"}
VALID_STRUCTURE = {"unset", "none", "epics", "epics_parallel"}
VALID_RIGOR = {"unset", "low", "standard", "high"}
PLANNING_STAGES = ("manifest", "bootstrap", "space_split")
VALID_STAGE_STATUS = {"pending", "reused", "synthesized", "delta", "skipped", "done"}


class SquaredSchemaDetected(ValueError):
    """Raised when an eigen-squared/eigen-lite-shaped dict is loaded as small state.

    Refusing here prevents eigen-small from clobbering a sibling pipeline's
    state file — the same guard eigen-lite applies against squared's schema.
    """


@dataclass
class StageMarker:
    status: str = "pending"
    path: Optional[str] = None

    def to_dict(self) -> dict:
        return {"status": self.status, "path": self.path}

    @classmethod
    def from_dict(cls, d: dict | None) -> "StageMarker":
        if not d:
            return cls()
        return cls(status=d.get("status", "pending"), path=d.get("path"))


@dataclass
class Wave:
    id: str = ""
    epics: list[str] = field(default_factory=list)
    parallel: bool = False
    epic_status: dict = field(default_factory=dict)  # epic -> pending|implemented
    goal_status: dict = field(default_factory=dict)   # epic -> pending|green
    goal_attempts: dict = field(default_factory=dict)  # epic -> int (red implementer round-trips; the circuit-breaker counter)
    review_status: str = "pending"                    # pending|done

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "epics": self.epics,
            "parallel": self.parallel,
            "epic_status": self.epic_status,
            "goal_status": self.goal_status,
            "goal_attempts": self.goal_attempts,
            "review_status": self.review_status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Wave":
        return cls(
            id=d.get("id", ""),
            epics=list(d.get("epics") or []),
            parallel=bool(d.get("parallel", False)),
            epic_status=d.get("epic_status") or {},
            goal_status=d.get("goal_status") or {},
            goal_attempts=d.get("goal_attempts") or {},
            review_status=d.get("review_status", "pending"),
        )


@dataclass
class SmallPipelineState:
    schema: str = SCHEMA
    initiative: str = ""
    phase: int = 1  # which phase SLOT this single-phase run occupies (1, or 2 to layer onto an existing repo)
    shape: str = "unknown"
    dials: dict = field(default_factory=lambda: {"structure": "unset", "rigor": "unset"})
    stages: dict = field(default_factory=lambda: {s: StageMarker() for s in PLANNING_STAGES})
    waves: list = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "initiative": self.initiative,
            "phase": self.phase,
            "shape": self.shape,
            "dials": self.dials,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "waves": [w.to_dict() for w in self.waves],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SmallPipelineState":
        nested = d.get("state") or {}
        if isinstance(nested, dict) and any(
            k in nested for k in ("time_split", "phases", "lite_plan")
        ):
            raise SquaredSchemaDetected(
                "state file carries an eigen-squared/eigen-lite schema; refusing "
                "to treat it as eigen-small state (a save would clobber it)."
            )
        stages = {
            s: StageMarker.from_dict((d.get("stages") or {}).get(s))
            for s in PLANNING_STAGES
        }
        return cls(
            schema=d.get("schema", SCHEMA),
            initiative=d.get("initiative", ""),
            phase=int(d.get("phase", 1)),
            shape=d.get("shape", "unknown"),
            dials=d.get("dials") or {"structure": "unset", "rigor": "unset"},
            stages=stages,
            waves=[Wave.from_dict(w) for w in (d.get("waves") or [])],
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def resolve_state_file(eigen_root: str | Path) -> Path:
    return _resolve_state_file(eigen_root, SMALL_STATE_RELATIVE_PATH)


def load_state(state_file: str | Path) -> Optional[SmallPipelineState]:
    """Load + parse small state. None if the file is absent.

    Propagates ``CorruptStateFile`` (malformed JSON) and ``SquaredSchemaDetected``
    (wrong schema) — both are signals the caller must surface, never swallow.
    """
    raw = load_raw_state(state_file)
    if raw is None:
        return None
    return SmallPipelineState.from_dict(raw)


def save_state(state: SmallPipelineState, state_file: str | Path) -> None:
    """Atomic save via eigen-core (sets updated_at inside save_raw_state)."""
    save_raw_state(state.to_dict(), state_file)


def create_initial_state(initiative: str, phase: int = 1) -> SmallPipelineState:
    now = datetime.now(timezone.utc).isoformat()
    return SmallPipelineState(initiative=initiative, phase=phase, created_at=now, updated_at=now)


def validate_state(state: SmallPipelineState) -> list[str]:
    """Return structural errors. Empty list = internally consistent."""
    errors: list[str] = []
    if state.shape not in VALID_SHAPES:
        errors.append(f"shape invalid: {state.shape!r} (valid: {sorted(VALID_SHAPES)})")
    structure = state.dials.get("structure", "unset")
    if structure not in VALID_STRUCTURE:
        errors.append(f"dials.structure invalid: {structure!r}")
    rigor = state.dials.get("rigor", "unset")
    if rigor not in VALID_RIGOR:
        errors.append(f"dials.rigor invalid: {rigor!r}")
    for s, marker in state.stages.items():
        if marker.status not in VALID_STAGE_STATUS:
            errors.append(f"stages.{s}.status invalid: {marker.status!r}")
    seen_ids: set[str] = set()
    for w in state.waves:
        if not isinstance(w, Wave):
            continue
        if w.id in seen_ids:
            errors.append(f"duplicate wave id: {w.id!r}")
        seen_ids.add(w.id)
        for e in w.epics:
            if e not in w.goal_status:
                errors.append(f"wave {w.id!r}: epic {e!r} missing from goal_status")
    return errors


__all__ = [
    "SCHEMA",
    "SMALL_STATE_RELATIVE_PATH",
    "VALID_RIGOR",
    "VALID_SHAPES",
    "VALID_STAGE_STATUS",
    "VALID_STRUCTURE",
    "PLANNING_STAGES",
    "SquaredSchemaDetected",
    "StageMarker",
    "Wave",
    "SmallPipelineState",
    "create_initial_state",
    "load_state",
    "resolve_state_file",
    "save_state",
    "validate_state",
]
