"""Tests for the eigen-core scheduler primitives.

These test the generic API directly (not the squared shim). Squared's
own tests in plugins/eigen-squared/cli/tests/test_scheduler.py exercise
the same retry/dedup logic via the re-export, providing belt-and-suspenders
coverage.
"""

import json
from datetime import datetime, timedelta, timezone

from eigen_core.cli.scheduler import (
    DEDUP_WINDOW_SECONDS,
    MAX_COMMAND_RETRIES,
    MAX_SCHEDULE_FAILURES,
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
