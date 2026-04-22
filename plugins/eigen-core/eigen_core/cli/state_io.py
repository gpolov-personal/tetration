"""Generic raw JSON I/O for pipeline state files.

Schema-agnostic — returns/accepts plain dicts. Typed wrappers
(`load_state` / `save_state` returning dataclasses) live in consumer
plugins on top of these primitives.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class CorruptStateFile(ValueError):
    """Raised by load_raw_state when a file exists but isn't valid JSON.

    Distinguishes corruption from a missing file — callers that treat
    missing as "fresh initiative" must NOT treat corruption the same way,
    or the next save silently wipes whatever was there.
    """


def resolve_state_file(
    eigen_root: str | Path,
    relative_path: str = "eigen_initiative/phases/pipeline_state.json",
) -> Path:
    """Resolve the pipeline state file path under the project root.

    Default matches eigen-squared's convention; eigen-lite passes its own
    relative path.
    """
    return Path(eigen_root) / relative_path


def load_raw_state(state_file: str | Path) -> Optional[dict]:
    """Load pipeline state as a plain dict.

    Returns None only if the file does not exist. A file that exists but
    has invalid JSON raises ``CorruptStateFile`` — the caller must decide
    whether to surface the error or roll back from a backup, rather than
    silently re-initialising on top of corrupted state.
    """
    path = Path(state_file)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CorruptStateFile(f"{path} is not valid JSON: {exc}") from exc


def save_raw_state(state: dict, state_file: str | Path) -> None:
    """Atomically serialize a state dict to JSON and write to disk.

    Writes to a sibling `.tmp` file first, then `os.replace` swaps it into
    place. A crash mid-write leaves either the old file intact or the new
    one committed — never a truncated half-write that ``load_raw_state``
    would raise CorruptStateFile on.

    Sets `updated_at` (top-level) to current UTC time before writing.
    Creates parent directories if needed.
    """
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(tmp_path, path)
