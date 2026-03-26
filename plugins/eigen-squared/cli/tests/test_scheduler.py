"""Tests for scheduler — retry logic and log handling."""

import json
import pytest

from cli.scheduler import check_retry, last_confirmed_entry, log_entry, MAX_COMMAND_RETRIES


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
            "status": "confirmed", "attempt": 1, "timestamp": "t1",
        }) + "\n")
        proceed, attempt = check_retry("deepen_time_split", "initiative", hook_log)
        assert proceed is True
        assert attempt == 1

    def test_same_command_increments_attempt(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "time_split", "context_key": "initiative",
            "status": "confirmed", "attempt": 1, "timestamp": "t1",
        }) + "\n")
        proceed, attempt = check_retry("time_split", "initiative", hook_log)
        assert proceed is True
        assert attempt == 2

    def test_max_retries_stops(self, tmp_path):
        hook_log = tmp_path / "hook_log.jsonl"
        hook_log.write_text(json.dumps({
            "command": "bootstrap", "context_key": "phase:P1",
            "status": "confirmed", "attempt": MAX_COMMAND_RETRIES, "timestamp": "t1",
        }) + "\n")
        proceed, attempt = check_retry("bootstrap", "phase:P1", hook_log)
        assert proceed is False


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
