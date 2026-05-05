"""Sync eigen-squared plugin assets into ``<eigen_root>/.opencode/``.

Pure-functional building blocks reused by ``cmd_sync_opencode``. Each
helper does one thing so tests can exercise them in isolation. The
operator-facing CLI command lives in ``cli/subcommands/__init__.py``.

Design choices baked in (multi-runtime-config-plan §3.5):

- **B5** — :func:`_reject_escaping_symlinks` is a ``shutil.copytree``
  ``ignore`` callback that filters out any entry whose symlink target
  would escape the source tree. Defends against a hostile plugin shipping
  ``commands/x.md -> /home/$USER/.ssh/id_ed25519``.
- **C2** — :func:`generate_ensemble_json` re-writes
  ``.opencode/ensemble.json`` from ``.eigen/runners.yaml`` on every sync.
  ``runners.yaml`` is the single source of truth; hand-editing
  ``ensemble.json`` is silently overwritten on the next sync.
- **C7 + D10** — :func:`write_sync_sentinel` drops a ``.sync_ok`` JSON
  manifest at the end. Doubles as (a) a gate the executor checks before
  spawning opencode runners and (b) an audit record (``synced_at``,
  ``plugin_version``, ``plugin_commit``, copied file counts).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

# Subdirectories copied verbatim from the plugin source into ``.opencode/``.
# Output layout matches what the OpenCode loader globs (``agent`` plural is
# accepted; we use the form the existing spike-agent-team uses for
# consistency).
ASSET_DIRS = ("commands", "skills", "agents")

# Files we never want to copy even when they live under ASSET_DIRS.
SKIP_NAMES = {".DS_Store", "__pycache__", "node_modules"}


class SyncError(RuntimeError):
    """Raised when sync cannot proceed safely (e.g. active opencode runs)."""


def plugin_root() -> Path:
    """Return the eigen-squared plugin source root.

    Pattern matches ``cli/__init__.py:14-16``: walk up from the CLI module
    so the helper works whether the plugin is installed via Claude Code
    or vendored.
    """
    return Path(__file__).resolve().parent.parent


def _reject_escaping_symlinks(source: str, names: Iterable[str]) -> set:
    """``shutil.copytree`` ignore callback: drop unwanted + escaping symlinks.

    A symlink escapes when its resolved real-path is not contained within
    the source tree's real-path. We compute that explicitly because
    ``Path.resolve(strict=True)`` would also fail on broken symlinks
    (whereas we just want to skip them).
    """
    src_root = Path(source).resolve()
    skipped = set()

    for name in names:
        if name in SKIP_NAMES:
            skipped.add(name)
            continue
        full = Path(source) / name
        if full.is_symlink():
            try:
                target = full.resolve()
            except OSError:
                # Broken symlink — refuse rather than crashing copytree.
                skipped.add(name)
                continue
            try:
                target.relative_to(src_root)
            except ValueError:
                skipped.add(name)
    return skipped


def _files_relative_to(root: Path) -> set[str]:
    """Set of forward-slash POSIX-style paths of every file under ``root``."""
    if not root.is_dir():
        return set()
    out = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root).as_posix())
    return out


def copy_assets(
    source_plugin: Path,
    target_dot_opencode: Path,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Copy ``commands/``, ``skills/``, ``agents/`` from plugin → target.

    Returns a per-directory file count so the sentinel manifest can record
    what was synced. Existing destinations are normally removed first so
    the sync is idempotent — but when the destination contains files NOT
    present in the plugin source, the sync would silently delete operator
    customizations (e.g. hand-added ``commands/local-spike.md``). Default
    behaviour is to refuse with a ``SyncError`` listing the surprises;
    pass ``force=True`` to skip the check and accept the data loss.
    """
    counts: dict[str, int] = {}
    for asset in ASSET_DIRS:
        src = source_plugin / asset
        if not src.is_dir():
            raise SyncError(
                f"plugin source missing required directory: {src} "
                f"(expected one of {ASSET_DIRS})"
            )
        dst = target_dot_opencode / asset
        if dst.exists():
            if not force:
                src_files = _files_relative_to(src)
                dst_files = _files_relative_to(dst)
                unknown = sorted(dst_files - src_files)
                if unknown:
                    sample = unknown[:5]
                    suffix = ", ..." if len(unknown) > len(sample) else ""
                    raise SyncError(
                        f"{dst} contains {len(unknown)} file(s) not present in the "
                        f"plugin source ({asset}/) — refusing to overwrite. "
                        f"Files: {sample}{suffix}. "
                        f"Move them aside, or pass --force to delete them."
                    )
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=_reject_escaping_symlinks, symlinks=False)
        counts[asset] = sum(1 for _ in dst.rglob("*") if _.is_file())
    return counts


def _read_yaml_strict(path: Path) -> dict:
    """Read a YAML mapping. Returns ``{}`` for missing/empty files;
    raises :class:`SyncError` on malformed YAML or non-mapping top level.

    Strict in the "operator-action" sense: this helper is for sync-time
    reads where degrading silently to ``{}`` would mask a typo in
    ``runners.yaml`` / ``profiles.yaml`` and cause the wrong runtime to
    be selected. That's distinct from
    ``eigen_core.cli.profiles._read_yaml`` which is intentionally
    lenient because it runs in the runtime hot path (resolve_profile)
    and must keep schedules running before the profile system is fully
    bootstrapped.
    """
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise SyncError(f"malformed YAML at {path}: {e}") from e
    if not isinstance(data, dict):
        raise SyncError(f"{path} must be a YAML mapping at the top level")
    return data


def _read_runners_yaml(eigen_root: Path) -> dict:
    """Read ``<eigen_root>/.eigen/runners.yaml`` strictly (E5 negative path)."""
    return _read_yaml_strict(eigen_root / ".eigen" / "runners.yaml")


def generate_ensemble_json(
    eigen_root: Path,
    target_dot_opencode: Path,
    profiles_path: Path,
) -> dict:
    """Re-write ``.opencode/ensemble.json`` from ``runners.yaml``.

    Resolution:

    1. If ``runners.yaml`` has ``opencode_default_profile``, use it.
       Otherwise pick ``default_profile`` if its runner is opencode.
    2. Look up the resolved profile in ``profiles.yaml`` to get the model id.
    3. ``models_by_agent`` (optional) maps agent names → model overrides.

    Returns the dict written to disk so callers can log changes.
    """
    runners = _read_runners_yaml(eigen_root)
    profiles = _read_yaml_strict(profiles_path).get("profiles") or {}

    # Pick the opencode-runtime profile to use for ensemble.defaultModel.
    chosen_profile = runners.get("opencode_default_profile")
    if not chosen_profile:
        candidate = runners.get("default_profile") or ""
        if candidate and (profiles.get(candidate) or {}).get("runner") == "opencode":
            chosen_profile = candidate

    default_model = ""
    if chosen_profile:
        spec = profiles.get(chosen_profile) or {}
        default_model = spec.get("model") or ""

    ensemble = {
        "dashboardPort": int(runners.get("dashboard_port") or 0),
        "defaultModel": default_model,
    }

    models_by_agent = runners.get("models_by_agent") or {}
    if isinstance(models_by_agent, dict) and models_by_agent:
        ensemble["modelsByAgent"] = {str(k): str(v) for k, v in models_by_agent.items()}

    target_dot_opencode.mkdir(parents=True, exist_ok=True)
    out_path = target_dot_opencode / "ensemble.json"
    out_path.write_text(json.dumps(ensemble, indent=2) + "\n")
    return ensemble


def _plugin_version(plugin_source: Path) -> str:
    manifest = plugin_source / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return ""
    try:
        return str(json.loads(manifest.read_text()).get("version") or "")
    except json.JSONDecodeError:
        return ""


def _plugin_commit(plugin_source: Path) -> str:
    """Best-effort: ``git rev-parse --short HEAD`` from the plugin source.

    Returns ``""`` on any failure (not in a git repo, git not on PATH, etc.).
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=plugin_source, capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def invalidate_sync_sentinel(target_dot_opencode: Path) -> None:
    """Remove ``.opencode/.sync_ok`` if present (idempotent).

    Called at the START of a sync so a SIGKILL/OOM/exception mid-sync
    cannot leave the previous (now-stale) sentinel pointing at a
    half-rebuilt ``.opencode/`` tree. The executor's pre-spawn check
    treats "no sentinel" as "do not run" — fail-closed by absence.
    """
    out_path = target_dot_opencode / ".sync_ok"
    out_path.unlink(missing_ok=True)


def write_sync_sentinel(
    target_dot_opencode: Path,
    plugin_source: Path,
    file_counts: dict[str, int],
    ensemble: dict,
) -> Path:
    """Drop ``.opencode/.sync_ok`` with a JSON manifest (C7 + D10).

    The presence of this file plus a valid ``synced_at`` is the gate the
    executor checks before spawning an opencode runner: a half-completed
    sync leaves no sentinel and the runner refuses to start. The manifest
    fields also serve as the audit record requested by D10.

    Atomicity: write to ``.sync_ok.tmp`` then ``os.replace`` onto the
    final name. ``Path.write_text`` opens-truncates-writes-closes and
    a SIGKILL between truncate and close would leave a torn sentinel
    (presence check passes, JSON parse fails). ``os.replace`` is an
    atomic rename on POSIX same-filesystem and on Windows, so the
    consumer either sees the previous sentinel (or none, after
    :func:`invalidate_sync_sentinel`) or the fully-written new one.
    """
    sentinel = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "plugin_version": _plugin_version(plugin_source),
        "plugin_commit": _plugin_commit(plugin_source),
        "files": file_counts,
        "ensemble": ensemble,
    }
    out_path = target_dot_opencode / ".sync_ok"
    tmp_path = target_dot_opencode / ".sync_ok.tmp"
    tmp_path.write_text(json.dumps(sentinel, indent=2) + "\n")
    os.replace(tmp_path, out_path)
    return out_path


def opencode_auth_ok() -> bool:
    """Best-effort auth check. Returns False when the operator has not
    run ``opencode auth login``. Still allows the sync to proceed —
    callers decide whether to warn or abort.
    """
    auth = Path(os.path.expanduser("~/.local/share/opencode/auth.json"))
    return auth.exists() and auth.stat().st_size > 0
