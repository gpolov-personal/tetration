"""Profile resolution for runtime-aware scheduling.

Two YAML files drive runtime selection:

- ``~/.claude-tasks/profiles.yaml`` — global catalogue mapping profile name
  to runner+model. Read by both the eigen-squared client (to compose the
  right prompt shape) and the claude-tasks daemon (to invoke the right
  runner binary).
- ``<eigen_root>/.eigen/runners.yaml`` — per-initiative selection: which
  profile each command should use, with a default fallback.

The client only needs ``runner_for`` to know whether to compose a
claude-style prompt or an opencode-style payload. Everything else
(model id, supports_append_system_prompt, env, etc.) lives server-side.

All readers degrade gracefully: missing files or unknown profile names
fall back to ``DEFAULT_PROFILE`` / ``DEFAULT_RUNNER`` so existing schedules
keep working before the profile system is bootstrapped.
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROFILES_PATH = Path.home() / ".claude-tasks" / "profiles.yaml"
RUNNERS_FILENAME = "runners.yaml"
DOT_DIR = ".eigen"

DEFAULT_PROFILE = "claude-opus"
DEFAULT_RUNNER = "claude"


def _read_yaml(path: Path) -> dict:
    """Read a YAML file. Returns ``{}`` on missing/empty/parse-error."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def runner_for(profile: str) -> str:
    """Return ``'claude'`` or ``'opencode'`` for the given profile name.

    Reads ``~/.claude-tasks/profiles.yaml``. Falls back to ``DEFAULT_RUNNER``
    if the profile is empty/unknown or the file is missing.
    """
    if not profile:
        return DEFAULT_RUNNER
    data = _read_yaml(PROFILES_PATH)
    profiles = data.get("profiles") or {}
    spec = profiles.get(profile) or {}
    return spec.get("runner") or DEFAULT_RUNNER


def resolve_profile(command: str, eigen_root: str) -> str:
    """Resolve the profile name for ``command`` in the initiative at ``eigen_root``.

    Lookup order:

    1. ``<eigen_root>/.eigen/runners.yaml`` → ``overrides[command]``
    2. ``<eigen_root>/.eigen/runners.yaml`` → ``default_profile``
    3. Hardcoded ``DEFAULT_PROFILE``
    """
    if not eigen_root:
        return DEFAULT_PROFILE
    runners_path = Path(eigen_root) / DOT_DIR / RUNNERS_FILENAME
    data = _read_yaml(runners_path)
    overrides = data.get("overrides") or {}
    if command and command in overrides:
        return overrides[command] or DEFAULT_PROFILE
    return data.get("default_profile") or DEFAULT_PROFILE


def command_name_for(command: str, profile: str) -> str:
    """Return the slash-command name for opencode-runtime tasks; ``''`` for claude.

    The slash-command name is transmitted via the ``command_name`` field of
    ``TaskRequest`` (separate from the prompt body), so the daemon can build
    ``opencode run --command <name>`` without parsing the prompt.
    """
    if runner_for(profile) == "opencode":
        return command
    return ""
