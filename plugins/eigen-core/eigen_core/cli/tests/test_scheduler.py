"""Tests for the eigen-core scheduler primitives.

These test the generic API directly (not the squared shim). Squared's
own tests in plugins/eigen-squared/cli/tests/test_scheduler.py exercise
the same retry/dedup logic via the re-export, providing belt-and-suspenders
coverage.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from eigen_core.cli import profiles
from eigen_core.cli.scheduler import (
    DEDUP_WINDOW_SECONDS,
    MAX_COMMAND_RETRIES,
    MAX_SCHEDULE_FAILURES,
    _compose_prompt,
    build_payload,
    check_retry,
    consecutive_schedule_failures,
    last_confirmed_entry,
    log_entry,
    resolve_hook_log,
)


def _old_timestamp() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=DEDUP_WINDOW_SECONDS + 60)).isoformat()


def _recent_timestamp() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()


class TestResolveHookLog:
    def test_default_dot_dir(self, tmp_path):
        assert resolve_hook_log(str(tmp_path)) == tmp_path / ".eigen" / "hook_log.jsonl"

    def test_custom_dot_dir(self, tmp_path):
        assert resolve_hook_log(str(tmp_path), dot_dir=".eigen-lite") == \
            tmp_path / ".eigen-lite" / "hook_log.jsonl"


class TestRetryLogic:
    def test_first_run_returns_attempt_1(self, tmp_path):
        proceed, attempt = check_retry("cmd", "ctx", tmp_path / "log.jsonl")
        assert proceed is True
        assert attempt == 1

    def test_dedup_window_blocks_rapid_retry(self, tmp_path):
        log = tmp_path / "log.jsonl"
        log.write_text(json.dumps({
            "command": "cmd", "context_key": "ctx", "status": "confirmed",
            "attempt": 1, "timestamp": _recent_timestamp(),
        }) + "\n")
        proceed, _ = check_retry("cmd", "ctx", log)
        assert proceed is False

    def test_outside_dedup_window_increments(self, tmp_path):
        log = tmp_path / "log.jsonl"
        log.write_text(json.dumps({
            "command": "cmd", "context_key": "ctx", "status": "confirmed",
            "attempt": 1, "timestamp": _old_timestamp(),
        }) + "\n")
        proceed, attempt = check_retry("cmd", "ctx", log)
        assert proceed is True
        assert attempt == 2

    def test_max_retries_stalls(self, tmp_path):
        log = tmp_path / "log.jsonl"
        log.write_text(json.dumps({
            "command": "cmd", "context_key": "ctx", "status": "confirmed",
            "attempt": MAX_COMMAND_RETRIES, "timestamp": _old_timestamp(),
        }) + "\n")
        proceed, _ = check_retry("cmd", "ctx", log)
        assert proceed is False

    def test_schedule_failures_circuit_breaker(self, tmp_path):
        log = tmp_path / "log.jsonl"
        lines = [
            json.dumps({"command": "cmd", "context_key": "ctx",
                        "status": "failed", "timestamp": f"t{i}"})
            for i in range(MAX_SCHEDULE_FAILURES)
        ]
        log.write_text("\n".join(lines) + "\n")
        proceed, _ = check_retry("cmd", "ctx", log)
        assert proceed is False


class TestConsecutiveScheduleFailures:
    def test_no_log_returns_zero(self, tmp_path):
        assert consecutive_schedule_failures("cmd", "ctx", tmp_path / "log.jsonl") == 0

    def test_counts_consecutive(self, tmp_path):
        log = tmp_path / "log.jsonl"
        lines = [
            json.dumps({"command": "cmd", "context_key": "ctx",
                        "status": "failed", "timestamp": f"t{i}"})
            for i in range(3)
        ]
        log.write_text("\n".join(lines) + "\n")
        assert consecutive_schedule_failures("cmd", "ctx", log) == 3

    def test_confirmed_breaks_streak(self, tmp_path):
        log = tmp_path / "log.jsonl"
        lines = [
            json.dumps({"command": "cmd", "context_key": "ctx",
                        "status": "failed", "timestamp": "t1"}),
            json.dumps({"command": "cmd", "context_key": "ctx",
                        "status": "confirmed", "attempt": 1, "timestamp": "t2"}),
            json.dumps({"command": "cmd", "context_key": "ctx",
                        "status": "failed", "timestamp": "t3"}),
        ]
        log.write_text("\n".join(lines) + "\n")
        assert consecutive_schedule_failures("cmd", "ctx", log) == 1


class TestLogEntry:
    def test_appends_with_timestamp(self, tmp_path):
        log = tmp_path / "log.jsonl"
        log_entry(log, {"action": "test"})
        entries = [json.loads(line) for line in log.read_text().strip().split("\n")]
        assert len(entries) == 1
        assert entries[0]["action"] == "test"
        assert "timestamp" in entries[0]


class TestLastConfirmedEntry:
    def test_finds_latest_confirmed_with_command(self, tmp_path):
        log = tmp_path / "log.jsonl"
        lines = [
            json.dumps({"command": "first", "status": "confirmed",
                        "attempt": 1, "timestamp": "t1"}),
            json.dumps({"command": "second", "status": "confirmed",
                        "attempt": 1, "timestamp": "t2"}),
        ]
        log.write_text("\n".join(lines) + "\n")
        entry = last_confirmed_entry(log)
        assert entry is not None
        assert entry["command"] == "second"

    def test_skips_entries_without_command_field(self, tmp_path):
        log = tmp_path / "log.jsonl"
        log.write_text(json.dumps({"status": "confirmed", "timestamp": "t1"}) + "\n")
        assert last_confirmed_entry(log) is None


@pytest.fixture
def claude_profile(tmp_path, monkeypatch):
    fake = tmp_path / "profiles.yaml"
    fake.write_text(
        "profiles:\n"
        "  claude-opus:\n"
        "    runner: claude\n"
        "  opencode-codex:\n"
        "    runner: opencode\n"
    )
    monkeypatch.setattr(profiles, "PROFILES_PATH", fake)


class TestComposePrompt:
    def test_claude_zero_extra_prompt(self, claude_profile):
        out = _compose_prompt("orchestrate-swarms", "claude-opus")
        assert 'Skill("orchestrate-swarms")' in out
        assert "Follow all its instructions completely." in out
        assert "\n\n" not in out

    def test_claude_with_extra_prompt(self, claude_profile):
        out = _compose_prompt("orchestrate-swarms", "claude-opus", extra_prompt="phase=2")
        assert out.endswith("phase=2")
        assert 'Skill("orchestrate-swarms")' in out

    def test_opencode_zero_arg_returns_empty(self, claude_profile):
        assert _compose_prompt("orchestrate-swarms", "opencode-codex") == ""

    def test_opencode_with_extra_prompt(self, claude_profile):
        out = _compose_prompt("orchestrate-swarms", "opencode-codex", extra_prompt="hello")
        assert out == "hello"

    def test_opencode_with_args_returns_json(self, claude_profile):
        out = _compose_prompt("orchestrate-swarms", "opencode-codex", args={"phase": 3})
        assert json.loads(out) == {"phase": 3}

    def test_unknown_profile_treated_as_claude(self, claude_profile):
        out = _compose_prompt("orchestrate-swarms", "missing", extra_prompt="x")
        assert 'Skill("orchestrate-swarms")' in out
        assert out.endswith("x")


class TestBuildPayload:
    def test_claude_payload_shape(self, claude_profile):
        p = build_payload(
            "time_split",
            skill="time-splitting",
            task_name="time_split-2026",
            eigen_root="/tmp/init",
            scheduled_at="2026-01-01T00:00:00+00:00",
        )
        assert p["name"] == "time_split-2026"
        assert p["profile"] == "claude-opus"  # from runners.yaml fallback
        assert p["command_name"] == ""  # claude runner
        assert p["working_dir"] == "/tmp/init"
        assert 'Skill("time-splitting")' in p["prompt"]
        assert "telegram_webhook" not in p

    def test_opencode_payload_shape(self, claude_profile, tmp_path):
        (tmp_path / ".eigen").mkdir()
        (tmp_path / ".eigen" / "runners.yaml").write_text(
            "default_profile: opencode-codex\n"
        )
        p = build_payload(
            "orchestrate_swarm",
            skill="orchestrating-swarms",
            task_name="orchestrate-2026",
            eigen_root=str(tmp_path),
            scheduled_at="2026-01-01T00:00:00+00:00",
            extra_prompt="phase=2",
        )
        assert p["profile"] == "opencode-codex"
        assert p["command_name"] == "orchestrate_swarm"
        assert p["prompt"] == "phase=2"  # extra_prompt becomes the body for opencode

    def test_explicit_profile_overrides_resolution(self, claude_profile, tmp_path):
        (tmp_path / ".eigen").mkdir()
        (tmp_path / ".eigen" / "runners.yaml").write_text(
            "default_profile: claude-opus\n"
        )
        p = build_payload(
            "time_split",
            skill="time-splitting",
            task_name="t",
            eigen_root=str(tmp_path),
            scheduled_at="t",
            profile="opencode-codex",
        )
        assert p["profile"] == "opencode-codex"
        assert p["command_name"] == "time_split"

    def test_webhooks_added_when_present(self, claude_profile):
        p = build_payload(
            "time_split",
            skill="s",
            task_name="t",
            eigen_root="/tmp",
            scheduled_at="ts",
            telegram_chat_id="123",
            slack_webhook="https://example/slack",
            discord_webhook="https://example/discord",
        )
        assert p["telegram_webhook"] == "123"
        assert p["slack_webhook"] == "https://example/slack"
        assert p["discord_webhook"] == "https://example/discord"
