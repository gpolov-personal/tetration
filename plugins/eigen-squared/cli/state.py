"""Load, save, and validate pipeline_state.json via typed models."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .models import (
    PipelineState,
    PhaseState,
    VALID_MAIN_STATUSES,
    VALID_DEEPEN_STATUSES,
    VALID_SWARM_STATUSES,
    VALID_PHASE_REVIEW_STATUSES,
    DEFAULT_RECOMMENDATIONS,
)


def resolve_state_file(eigen_root: str | Path) -> Path:
    return Path(eigen_root) / "eigen_initiative" / "phases" / "pipeline_state.json"


@contextmanager
def locked_state(state_file: str | Path) -> Iterator[None]:
    """Serialize concurrent load→mutate→save cycles via POSIX ``flock``.

    B1 — 1.1's atomic ``os.replace`` prevents *torn writes* (a reader
    never sees a truncated file), but it does not prevent *lost
    updates*: if two processes both ``load_state → mutate → save_state``
    concurrently, the second save silently overwrites the first
    mutation. ``eigen-watchdog.sh``'s ``flock`` only serializes the
    watchdog against itself — not against already-spawned LLM tasks or
    manual CLI invocations (e.g. ``eigen-squared add-recommendation``).

    Callers wrap the full load→mutate→save block:

        with locked_state(sf):
            state = load_state(sf)
            ...
            save_state(state, sf)

    The lock file lives next to the state file (``pipeline_state.json.lock``).
    ``fcntl.flock`` is advisory — only processes that also call
    ``locked_state`` are serialized. That is the correct scope here:
    all writers come through this module. ``LOCK_EX`` blocks; we do
    not time out, because the held region is a handful of in-memory
    operations plus one ``os.replace`` — any multi-second block means
    something is very wrong and failing loudly is better than silently
    dropping writes.
    """
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / (path.name + ".lock")
    # O_CREAT|O_WRONLY is enough — flock attaches to the open file
    # description, not to the file contents.
    fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def load_state(state_file: str | Path) -> Optional[PipelineState]:
    """Load and parse pipeline_state.json into a PipelineState model.

    Returns None if the file does not exist or contains invalid JSON.
    """
    path = Path(state_file)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return PipelineState.from_dict(raw)


def save_state(state: PipelineState, state_file: str | Path) -> None:
    """Serialize PipelineState to JSON and write to disk via atomic rename.

    1.1 — writes the new content to a temporary file in the same directory
    and then ``os.replace()``-s it into place. On POSIX this is an atomic
    rename within a single filesystem, so a concurrent reader either sees
    the previous complete file or the new complete file, never a partial
    one. (Note: full crash durability across power loss additionally
    requires an ``fsync`` on the parent directory; we don't do that here
    because the pipeline_state.json can always be rebuilt from the
    on-disk manifests + git log if a hard crash lands between rename and
    directory flush — atomicity vs. readers is the invariant we need.)

    ``tempfile.NamedTemporaryFile(dir=parent)`` guarantees the temp file
    lands on the same filesystem as the target — required for the
    rename to be atomic.

    S7 — mirror the *existing* file's mode onto the tempfile before the
    rename. ``NamedTemporaryFile`` creates at 0o600, and ``os.replace``
    preserves the source's mode on POSIX, so without this step the first
    post-merge save would silently downgrade an 0o644 state file to
    0o600 and break downstream readers running under a different uid.

    Sets updated_at to current UTC time before writing.
    """
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2) + "\n"

    # Capture the current mode (if the file exists) so we can restore it
    # after os.replace. Fall back to 0o644 for freshly-created states —
    # matches the default umask on most deploys and is what `touch` would
    # produce.
    try:
        target_mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        target_mode = 0o644

    # delete=False because we rename it ourselves; the context manager
    # only exists so the file handle is closed before the rename.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(payload)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    try:
        os.chmod(tmp_path, target_mode)
        os.replace(tmp_path, path)
    except OSError:
        # Best-effort cleanup if the chmod or rename itself failed.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def create_initial_state(
    initiative: str,
    phase_count: int,
) -> PipelineState:
    """Create a fresh PipelineState with all phases initialized.

    This replaces the 40+ lines of initialization logic in time_split.
    Every phase gets bootstrap_converge, space_split_converge,
    phase_review, and empty plans.
    """
    now = datetime.now(timezone.utc).isoformat()
    phases = {}
    for i in range(1, phase_count + 1):
        phases[str(i)] = PhaseState()

    return PipelineState(
        schema_version="2.0.0",
        initiative=initiative,
        created_at=now,
        updated_at=now,
        phases=phases,
        recommendations=dict(DEFAULT_RECOMMENDATIONS),
    )


def validate_state(state: PipelineState) -> list[str]:
    """Validate a PipelineState and return a list of errors (empty = valid)."""
    errors: list[str] = []

    if state.time_split.status not in VALID_MAIN_STATUSES:
        errors.append(f"time_split.status invalid: {state.time_split.status!r}")

    if state.deepen_time_split.status not in VALID_DEEPEN_STATUSES:
        errors.append(
            f"deepen_time_split.status invalid: {state.deepen_time_split.status!r}"
        )

    for phase_key, phase in state.phases.items():
        prefix = f"phases[{phase_key}]"

        if phase.bootstrap_converge.status not in VALID_MAIN_STATUSES:
            errors.append(
                f"{prefix}.bootstrap_converge.status invalid: "
                f"{phase.bootstrap_converge.status!r}"
            )
        if phase.space_split_converge.status not in VALID_MAIN_STATUSES:
            errors.append(
                f"{prefix}.space_split_converge.status invalid: "
                f"{phase.space_split_converge.status!r}"
            )
        if phase.phase_review.status not in VALID_PHASE_REVIEW_STATUSES:
            errors.append(
                f"{prefix}.phase_review.status invalid: "
                f"{phase.phase_review.status!r}"
            )

        for epic_key, epic_plan in phase.plans.items():
            eprefix = f"{prefix}.plans[{epic_key}]"
            if epic_plan.plan_epic_converge.status not in VALID_MAIN_STATUSES:
                errors.append(
                    f"{eprefix}.plan_epic_converge.status invalid: "
                    f"{epic_plan.plan_epic_converge.status!r}"
                )
            if epic_plan.swarm_execution.status not in VALID_SWARM_STATUSES:
                errors.append(
                    f"{eprefix}.swarm_execution.status invalid: "
                    f"{epic_plan.swarm_execution.status!r}"
                )

    return errors
