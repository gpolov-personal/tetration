"""Tests for the profile resolution helpers."""

from pathlib import Path

import pytest

from eigen_core.cli import profiles


@pytest.fixture
def fake_profiles(tmp_path, monkeypatch):
    """Point PROFILES_PATH at a tmp file the test can write."""
    fake = tmp_path / "profiles.yaml"
    monkeypatch.setattr(profiles, "PROFILES_PATH", fake)
    return fake


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


class TestRunnerFor:
    def test_missing_file_returns_default(self, fake_profiles):
        assert profiles.runner_for("anything") == profiles.DEFAULT_RUNNER

    def test_empty_profile_returns_default(self, fake_profiles):
        assert profiles.runner_for("") == profiles.DEFAULT_RUNNER

    def test_known_claude_profile(self, fake_profiles):
        _write(fake_profiles, "profiles:\n  claude-opus:\n    runner: claude\n")
        assert profiles.runner_for("claude-opus") == "claude"

    def test_known_opencode_profile(self, fake_profiles):
        _write(fake_profiles, "profiles:\n  opencode-codex:\n    runner: opencode\n")
        assert profiles.runner_for("opencode-codex") == "opencode"

    def test_unknown_profile_falls_back(self, fake_profiles):
        _write(fake_profiles, "profiles:\n  claude-opus:\n    runner: claude\n")
        assert profiles.runner_for("missing") == profiles.DEFAULT_RUNNER

    def test_malformed_yaml_falls_back(self, fake_profiles):
        _write(fake_profiles, "profiles: {[broken")
        assert profiles.runner_for("claude-opus") == profiles.DEFAULT_RUNNER

    def test_profile_without_runner_field_falls_back(self, fake_profiles):
        _write(fake_profiles, "profiles:\n  weird:\n    model: x\n")
        assert profiles.runner_for("weird") == profiles.DEFAULT_RUNNER


class TestResolveProfile:
    def test_empty_root_returns_default_profile(self):
        assert profiles.resolve_profile("time_split", "") == profiles.DEFAULT_PROFILE

    def test_missing_runners_yaml_returns_default(self, tmp_path):
        assert profiles.resolve_profile("time_split", str(tmp_path)) == profiles.DEFAULT_PROFILE

    def test_default_profile_used_when_no_override(self, tmp_path):
        _write(tmp_path / ".eigen" / "runners.yaml", "default_profile: opencode-codex\n")
        assert profiles.resolve_profile("time_split", str(tmp_path)) == "opencode-codex"

    def test_override_wins_over_default(self, tmp_path):
        _write(
            tmp_path / ".eigen" / "runners.yaml",
            "default_profile: claude-opus\n"
            "overrides:\n"
            "  orchestrate_swarm: opencode-codex\n",
        )
        assert profiles.resolve_profile("orchestrate_swarm", str(tmp_path)) == "opencode-codex"
        assert profiles.resolve_profile("time_split", str(tmp_path)) == "claude-opus"

    def test_empty_default_falls_back_to_hardcoded(self, tmp_path):
        _write(tmp_path / ".eigen" / "runners.yaml", "default_profile:\n")
        assert profiles.resolve_profile("time_split", str(tmp_path)) == profiles.DEFAULT_PROFILE


class TestCommandNameFor:
    def test_claude_profile_returns_empty(self, fake_profiles):
        _write(fake_profiles, "profiles:\n  claude-opus:\n    runner: claude\n")
        assert profiles.command_name_for("time_split", "claude-opus") == ""

    def test_opencode_profile_returns_command(self, fake_profiles):
        _write(fake_profiles, "profiles:\n  opencode-codex:\n    runner: opencode\n")
        assert profiles.command_name_for("orchestrate_swarm", "opencode-codex") == "orchestrate_swarm"

    def test_unknown_profile_treated_as_claude(self, fake_profiles):
        assert profiles.command_name_for("time_split", "missing") == ""
