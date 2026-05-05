"""Tests for the sync.py building blocks (Fase 3 / sync cluster)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cli import sync


# ── B5 — symlink escape rejection ────────────────────────────────────────


def test_reject_escaping_symlinks_drops_external_target(tmp_path):
    src = tmp_path / "src"
    outside = tmp_path / "secret"
    src.mkdir()
    outside.write_text("private")

    (src / "ok.md").write_text("safe content")
    (src / "evil.md").symlink_to(outside)

    skipped = sync._reject_escaping_symlinks(str(src), os.listdir(src))
    assert "evil.md" in skipped
    assert "ok.md" not in skipped


def test_reject_escaping_symlinks_keeps_internal_symlinks(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "real.md").write_text("x")
    (src / "alias.md").symlink_to(src / "real.md")

    skipped = sync._reject_escaping_symlinks(str(src), os.listdir(src))
    assert "alias.md" not in skipped


def test_copy_assets_blocks_escaping_symlink(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("private")

    for d in sync.ASSET_DIRS:
        (plugin / d).mkdir()
    (plugin / "commands" / "x.md").write_text("ok")
    (plugin / "commands" / "evil.md").symlink_to(secret)

    target = tmp_path / "out" / ".opencode"
    counts = sync.copy_assets(plugin, target)

    assert (target / "commands" / "x.md").read_text() == "ok"
    assert not (target / "commands" / "evil.md").exists()
    assert counts["commands"] == 1


def test_copy_assets_fails_on_missing_dir(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    # only commands/ — skills/ + agents/ missing
    (plugin / "commands").mkdir()

    with pytest.raises(sync.SyncError, match="missing required directory"):
        sync.copy_assets(plugin, tmp_path / "out")


def _build_minimal_plugin(plugin: Path) -> None:
    for d in sync.ASSET_DIRS:
        (plugin / d).mkdir(parents=True)
    (plugin / "commands" / "ship_a.md").write_text("plugin a")
    (plugin / "commands" / "ship_b.md").write_text("plugin b")
    (plugin / "skills" / "skill_a.md").write_text("plugin skill")
    (plugin / "agents" / "agent_a.md").write_text("plugin agent")


def test_copy_assets_refuses_to_clobber_user_files_without_force(tmp_path):
    """Pins must-fix #5 from PR #33 review.

    Pre-fix copy_assets did `if dst.exists(): rmtree(dst)` and silently
    deleted any operator-customized files in the .opencode/ asset trees.
    Default behaviour must now refuse with an actionable SyncError.
    """
    plugin = tmp_path / "plugin"
    _build_minimal_plugin(plugin)
    target = tmp_path / "out" / ".opencode"
    (target / "commands").mkdir(parents=True)
    user_file = target / "commands" / "user_local_spike.md"
    user_file.write_text("HAND-EDITED — DO NOT WIPE")

    with pytest.raises(sync.SyncError, match="user_local_spike.md"):
        sync.copy_assets(plugin, target)

    # User file must still be on disk.
    assert user_file.exists()
    assert user_file.read_text() == "HAND-EDITED — DO NOT WIPE"


def test_copy_assets_force_overwrites_user_files(tmp_path):
    """``--force`` is the documented escape hatch — tests it actually works."""
    plugin = tmp_path / "plugin"
    _build_minimal_plugin(plugin)
    target = tmp_path / "out" / ".opencode"
    (target / "commands").mkdir(parents=True)
    user_file = target / "commands" / "user_local_spike.md"
    user_file.write_text("ABOUT TO BE WIPED ON PURPOSE")

    counts = sync.copy_assets(plugin, target, force=True)

    # Plugin files copied, user file gone.
    assert (target / "commands" / "ship_a.md").exists()
    assert not user_file.exists()
    assert counts["commands"] == 2  # ship_a + ship_b


def test_copy_assets_no_user_files_no_force_needed(tmp_path):
    """If dst exists but contains only files that ARE in source, sync
    proceeds without --force (the "second sync of an unchanged install"
    case must remain frictionless)."""
    plugin = tmp_path / "plugin"
    _build_minimal_plugin(plugin)
    target = tmp_path / "out" / ".opencode"

    # First sync — fresh, no clobber concern.
    counts1 = sync.copy_assets(plugin, target)
    assert counts1["commands"] == 2

    # Second sync — dst now mirrors src exactly, no unknown files.
    counts2 = sync.copy_assets(plugin, target)
    assert counts2["commands"] == 2


# ── C2 — ensemble.json regeneration ─────────────────────────────────────


def _write(p: Path, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_generate_ensemble_picks_opencode_default_profile(tmp_path):
    eigen_root = tmp_path / "init"
    profiles_path = tmp_path / "profiles.yaml"
    target = tmp_path / "init" / ".opencode"

    _write(eigen_root / ".eigen" / "runners.yaml",
           "default_profile: claude-opus\nopencode_default_profile: opencode-codex\n")
    _write(profiles_path,
           "profiles:\n"
           "  claude-opus:\n    runner: claude\n    model: claude-opus-4-7\n"
           "  opencode-codex:\n    runner: opencode\n    model: openai/gpt-5.3-codex\n")

    ensemble = sync.generate_ensemble_json(eigen_root, target, profiles_path)
    assert ensemble["defaultModel"] == "openai/gpt-5.3-codex"
    on_disk = json.loads((target / "ensemble.json").read_text())
    assert on_disk == ensemble


def test_generate_ensemble_falls_back_to_opencode_default_profile(tmp_path):
    """When default_profile resolves to opencode runner, use it for ensemble."""
    eigen_root = tmp_path / "init"
    profiles_path = tmp_path / "profiles.yaml"

    _write(eigen_root / ".eigen" / "runners.yaml", "default_profile: opencode-codex\n")
    _write(profiles_path,
           "profiles:\n  opencode-codex:\n    runner: opencode\n    model: m\n")

    ensemble = sync.generate_ensemble_json(eigen_root, tmp_path / "out", profiles_path)
    assert ensemble["defaultModel"] == "m"


def test_generate_ensemble_ignores_claude_default(tmp_path):
    """A claude-runner default_profile must not become the ensemble defaultModel."""
    eigen_root = tmp_path / "init"
    profiles_path = tmp_path / "profiles.yaml"

    _write(eigen_root / ".eigen" / "runners.yaml", "default_profile: claude-opus\n")
    _write(profiles_path,
           "profiles:\n  claude-opus:\n    runner: claude\n    model: claude-opus-4-7\n")

    ensemble = sync.generate_ensemble_json(eigen_root, tmp_path / "out", profiles_path)
    assert ensemble["defaultModel"] == ""


def test_generate_ensemble_includes_models_by_agent(tmp_path):
    eigen_root = tmp_path / "init"
    profiles_path = tmp_path / "profiles.yaml"

    _write(eigen_root / ".eigen" / "runners.yaml",
           "opencode_default_profile: opencode-codex\n"
           "models_by_agent:\n"
           "  security-sentinel: openai/gpt-5.3-codex\n"
           "  performance-oracle: minimax/minimax-m2\n")
    _write(profiles_path,
           "profiles:\n  opencode-codex:\n    runner: opencode\n    model: m\n")

    ensemble = sync.generate_ensemble_json(eigen_root, tmp_path / "out", profiles_path)
    assert ensemble["modelsByAgent"]["security-sentinel"] == "openai/gpt-5.3-codex"
    assert ensemble["modelsByAgent"]["performance-oracle"] == "minimax/minimax-m2"


def test_generate_ensemble_handles_missing_runners_yaml(tmp_path):
    eigen_root = tmp_path / "init"
    eigen_root.mkdir()
    ensemble = sync.generate_ensemble_json(eigen_root, tmp_path / "out", tmp_path / "absent.yaml")
    assert ensemble == {"dashboardPort": 0, "defaultModel": ""}


def test_generate_ensemble_rejects_malformed_yaml(tmp_path):
    eigen_root = tmp_path / "init"
    profiles_path = tmp_path / "profiles.yaml"

    _write(eigen_root / ".eigen" / "runners.yaml",
           "default_profile: claude-opus\n  bad indent: oops\n")
    _write(profiles_path, "profiles: {}\n")

    with pytest.raises(sync.SyncError, match="malformed YAML"):
        sync.generate_ensemble_json(eigen_root, tmp_path / "out", profiles_path)


# ── C7 + D10 — sentinel manifest ────────────────────────────────────────


def test_sentinel_shape(tmp_path):
    target = tmp_path / ".opencode"
    target.mkdir()
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "eigen-squared", "version": "9.9.9"})
    )

    counts = {"commands": 5, "skills": 3, "agents": 12}
    ensemble = {"dashboardPort": 0, "defaultModel": "openai/gpt-5.3-codex"}

    out = sync.write_sync_sentinel(target, plugin, counts, ensemble)
    body = json.loads(out.read_text())

    assert body["plugin_version"] == "9.9.9"
    assert body["files"] == counts
    assert body["ensemble"] == ensemble
    assert "synced_at" in body
    # plugin_commit is best-effort; either populated or empty string
    assert "plugin_commit" in body


def test_invalidate_sync_sentinel_removes_existing(tmp_path):
    target = tmp_path / ".opencode"
    target.mkdir()
    sentinel = target / ".sync_ok"
    sentinel.write_text("stale-content")
    assert sentinel.exists()

    sync.invalidate_sync_sentinel(target)
    assert not sentinel.exists()


def test_invalidate_sync_sentinel_idempotent_when_missing(tmp_path):
    target = tmp_path / ".opencode"
    target.mkdir()
    # No .sync_ok — must not raise.
    sync.invalidate_sync_sentinel(target)


def test_write_sentinel_uses_atomic_replace_no_tmp_left(tmp_path):
    """Pins must-fix #2: torn-write protection.

    The previous implementation called ``Path.write_text`` directly on the
    final ``.sync_ok``; SIGKILL between the open(O_TRUNC) and the close
    would leave a torn JSON. The new implementation writes to
    ``.sync_ok.tmp`` and ``os.replace``s into place. Two assertions:
    (a) the final sentinel is valid JSON, and (b) no ``.sync_ok.tmp`` is
    left behind on success.
    """
    target = tmp_path / ".opencode"
    target.mkdir()
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "eigen-squared", "version": "1.0.0"})
    )

    out = sync.write_sync_sentinel(
        target, plugin,
        {"commands": 1, "skills": 1, "agents": 1},
        {"dashboardPort": 0, "defaultModel": ""},
    )

    assert out.exists()
    json.loads(out.read_text())  # must parse
    assert not (target / ".sync_ok.tmp").exists()
