"""Tests for scheduler — retry logic and log handling."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from cli.scheduler import (
    check_retry,
    last_confirmed_entry,
    log_entry,
    DEDUP_WINDOW_SECONDS,
    MAX_COMMAND_RETRIES,
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
