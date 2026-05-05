"""Daemon compatibility check (C5).

Before scheduling or installing, the eigen-squared client should confirm
the claude-tasks daemon understands the fields it intends to send. The
daemon advertises capabilities at ``GET /api/v1/version``:

    {
      "version":         "<build>",
      "schema_version":  2,
      "supports":        ["profile", "command_name", ...],
      "profiles":        ["claude-opus", "opencode-codex", ...]
    }

`check_daemon_compat` returns a small result struct so callers can decide
whether to abort with an actionable error. The check is intentionally
permissive on transport-level failures — when the daemon is unreachable
the operator sees a clear "could not reach" message rather than a panic
deep inside the install pipeline.

Stdlib-only: depends on `urllib.request` and `json`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

# Capabilities the eigen-squared client expects when scheduling
# multi-runtime tasks. Bump together with the Go-side `supports[]`.
DEFAULT_REQUIRED_SUPPORTS = ("profile", "command_name", "resolved_runner", "resolved_model")
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass
class CompatResult:
    ok: bool
    reason: str = ""
    version: str = ""
    schema_version: int = 0
    supports: List[str] = field(default_factory=list)
    profiles: List[str] = field(default_factory=list)


def _normalise_url(api_url: str) -> str:
    """Strip trailing slashes so we can blindly append `/api/v1/version`."""
    return api_url.rstrip("/")


def check_daemon_compat(
    api_url: str,
    required_supports: Optional[List[str]] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CompatResult:
    """GET ``/api/v1/version`` and validate ``supports[]``.

    Returns a :class:`CompatResult`. ``ok`` is True iff every entry in
    ``required_supports`` is present in the daemon's ``supports`` array.
    Network/parse errors yield ``ok=False`` with an actionable ``reason``.
    """
    if required_supports is None:
        required_supports = list(DEFAULT_REQUIRED_SUPPORTS)

    url = _normalise_url(api_url) + "/api/v1/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.URLError as e:
        return CompatResult(
            ok=False,
            reason=f"could not reach claude-tasks daemon at {url}: {e.reason}",
        )
    except (TimeoutError, OSError) as e:
        return CompatResult(
            ok=False,
            reason=f"could not reach claude-tasks daemon at {url}: {e}",
        )

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        return CompatResult(
            ok=False,
            reason=f"daemon at {url} returned non-JSON response: {e}",
        )
    if not isinstance(data, dict):
        return CompatResult(
            ok=False,
            reason=f"daemon at {url} returned non-object response: {type(data).__name__}",
        )

    supports = data.get("supports") or []
    missing = [c for c in required_supports if c not in supports]
    if missing:
        return CompatResult(
            ok=False,
            reason=(
                f"claude-tasks daemon at {url} is missing required capabilities: "
                f"{missing}. Daemon supports={supports}. "
                f"Upgrade claude-tasks before installing eigen-squared with multi-runtime profiles."
            ),
            version=data.get("version", ""),
            schema_version=int(data.get("schema_version") or 0),
            supports=list(supports),
            profiles=list(data.get("profiles") or []),
        )

    return CompatResult(
        ok=True,
        version=data.get("version", ""),
        schema_version=int(data.get("schema_version") or 0),
        supports=list(supports),
        profiles=list(data.get("profiles") or []),
    )
