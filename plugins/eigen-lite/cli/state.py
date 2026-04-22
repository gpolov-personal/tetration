"""Typed load/save/validate for lite pipeline state.

Wraps ``eigen_core.cli.state_io`` (raw JSON I/O) and
``cli.models_lite.LitePipelineState`` (typed schema) into one place so
subcommands don't reach into either directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eigen_core.cli.state_io import (
    load_raw_state,
    resolve_state_file as _resolve_state_file,
    save_raw_state,
)

from .models_lite import (
    LITE_STATE_RELATIVE_PATH,
    LiteEpicState,
    LitePipelineState,
    VALID_LITE_PLAN_STATUSES,
    VALID_LITE_REVIEW_STATUSES,
    VALID_LITE_SWARM_STATUSES,
)


def resolve_state_file(eigen_root: str | Path) -> Path:
    """Where lite expects to find pipeline_state_lite.json."""
    return _resolve_state_file(eigen_root, LITE_STATE_RELATIVE_PATH)


def load_state(state_file: str | Path) -> Optional[LitePipelineState]:
    """Load + parse lite state. Returns None if the file doesn't exist.

    Propagates :class:`eigen_core.cli.state_io.CorruptStateFile` when the
    file exists but is malformed JSON, and
    :class:`cli.models_lite.SquaredSchemaDetected` when a squared-shaped
    dict is found — both are signals the caller must surface, never swallow.
    """
    raw = load_raw_state(state_file)
    if raw is None:
        return None
    return LitePipelineState.from_dict(raw)


def save_state(state: LitePipelineState, state_file: str | Path) -> None:
    """Atomic save via eigen-core. Sets updated_at inside save_raw_state."""
    save_raw_state(state.to_dict(), state_file)


def create_initial_state(feature_set: str, epic_count: int = 0) -> LitePipelineState:
    """Fresh state with empty plan and empty epics dict.

    Callers typically use epic_count=0 at init time; the real count is
    written by ``lite_plan`` Stage D (the ``init-epics`` subcommand).
    """
    now = datetime.now(timezone.utc).isoformat()
    return LitePipelineState(
        feature_set=feature_set,
        epic_count=epic_count,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# validate_state_lite — covers H3, M2, M3, M4, M5 from the gap audit
# ---------------------------------------------------------------------------

def validate_state_lite(state: LitePipelineState) -> list[str]:
    """Return structural errors. Empty list = state is internally consistent.

    Enforces:
      - Status fields are in their allowed sets.
      - Epic keys are stringified positive ints starting at "1".
      - ``epic_count`` matches ``len(epics)`` once epics have been initialized.
      - At most one epic is marked ``is_e2e_epic=True``, and if present it is
        the max epic key (E2E epic is always last).
      - ``integration_branch`` matches ``feat/P1.E<key>`` when set.
      - ``swarm.status == "converged"`` iff ``swarm.convergence.converged``.
      - ``stages_completed`` values are within the known grammar
        ``{A, B, C, D, E:1, E:2, ...}`` limited by ``epic_count``.
      - When ``lite_plan.convergence.converged`` is True, every feature-epic
        ``E:<n>`` marker is present.
    """
    errors: list[str] = []

    # Main command statuses
    if state.lite_plan.status not in VALID_LITE_PLAN_STATUSES:
        errors.append(f"lite_plan.status invalid: {state.lite_plan.status!r}")

    # Epic keys + count coherence
    if state.epic_count and state.epic_count != len(state.epics):
        errors.append(
            f"epic_count ({state.epic_count}) != len(epics) "
            f"({len(state.epics)})"
        )

    if state.epics:
        raw_keys = list(state.epics.keys())
        parsed: list[int] = []
        for k in raw_keys:
            try:
                n = int(k)
            except (ValueError, TypeError):
                errors.append(f"epics: non-integer key {k!r}")
                continue
            if n < 1:
                errors.append(f"epics: non-positive key {k!r}")
            else:
                parsed.append(n)

        if sorted(parsed) != parsed or parsed != list(range(1, len(parsed) + 1)):
            errors.append(
                f"epics: keys must be contiguous starting at 1; got "
                f"{sorted(parsed)}"
            )

        # E2E epic constraints
        e2e_keys = [int(k) for k, e in state.epics.items() if e.is_e2e_epic]
        if len(e2e_keys) > 1:
            errors.append(f"multiple epics marked is_e2e_epic: {e2e_keys}")
        elif e2e_keys and parsed and max(e2e_keys) != max(parsed):
            errors.append(
                f"is_e2e_epic must be the last epic; "
                f"got E{e2e_keys[0]} but max epic is E{max(parsed)}"
            )

    # Per-epic invariants
    for key, epic in state.epics.items():
        prefix = f"epics[{key}]"
        _validate_epic(epic, key, prefix, errors)

    # stages_completed grammar
    _validate_stages_completed(state, errors)

    return errors


def _validate_epic(
    epic: LiteEpicState,
    key: str,
    prefix: str,
    errors: list[str],
) -> None:
    swarm = epic.lite_swarm
    review = epic.lite_review

    if swarm.status not in VALID_LITE_SWARM_STATUSES:
        errors.append(f"{prefix}.lite_swarm.status invalid: {swarm.status!r}")
    if review.status not in VALID_LITE_REVIEW_STATUSES:
        errors.append(f"{prefix}.lite_review.status invalid: {review.status!r}")

    # M3: top-level status vs convergence flag must agree for the 'converged' state
    if swarm.status == "converged" and not swarm.convergence.converged:
        errors.append(
            f"{prefix}.lite_swarm: status='converged' but "
            f"convergence.converged=False"
        )
    if swarm.convergence.converged and swarm.status not in ("converged", "iterating", "pr_created"):
        # converged flag can be set while status is still in a transient state
        # only during the brief auto-merge window — otherwise it's a drift.
        errors.append(
            f"{prefix}.lite_swarm: convergence.converged=True but "
            f"status={swarm.status!r}"
        )

    # integration_branch shape
    if swarm.integration_branch:
        expected = f"feat/P1.E{int(key)}" if key.isdigit() else None
        if expected and swarm.integration_branch != expected:
            errors.append(
                f"{prefix}.lite_swarm.integration_branch "
                f"{swarm.integration_branch!r} != expected {expected!r}"
            )


def _validate_stages_completed(
    state: LitePipelineState, errors: list[str]
) -> None:
    stages = state.lite_plan.stages_completed
    count = state.epic_count or len(state.epics)
    valid = {"A", "B", "C", "D"} | {f"E:{i}" for i in range(1, max(count, 0) + 1)}
    for marker in stages:
        if marker not in valid:
            errors.append(
                f"lite_plan.stages_completed: unknown marker {marker!r} "
                f"(valid: sorted A..D and E:1..E:{count})"
            )

    # M2: if plan claims converged, every feature-epic E:<n> must be present
    if state.lite_plan.convergence.converged and count > 0:
        missing = [
            f"E:{i}" for i in range(1, count + 1) if f"E:{i}" not in stages
        ]
        if missing:
            errors.append(
                f"lite_plan.convergence.converged=True but missing "
                f"stage markers: {missing}"
            )


__all__ = [
    "create_initial_state",
    "load_state",
    "resolve_state_file",
    "save_state",
    "validate_state_lite",
]
