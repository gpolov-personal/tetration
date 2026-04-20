"""Tests for raw state I/O primitives."""

import json

import pytest

from eigen_core.cli.state_io import (
    CorruptStateFile,
    load_raw_state,
    resolve_state_file,
    save_raw_state,
)


class TestResolveStateFile:
    def test_default_path(self, tmp_path):
        resolved = resolve_state_file(tmp_path)
        assert resolved == tmp_path / "eigen_initiative" / "phases" / "pipeline_state.json"

    def test_custom_relative_path(self, tmp_path):
        resolved = resolve_state_file(tmp_path, "custom/state.json")
        assert resolved == tmp_path / "custom" / "state.json"


class TestLoadRawState:
    def test_missing_file_returns_none(self, tmp_path):
        assert load_raw_state(tmp_path / "nope.json") is None

    def test_invalid_json_raises_corrupt(self, tmp_path):
        """Corruption is never 'fresh init' — surface it so we don't wipe state."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json{")
        with pytest.raises(CorruptStateFile):
            load_raw_state(bad)

    def test_valid_json_returns_dict(self, tmp_path):
        good = tmp_path / "good.json"
        good.write_text('{"a": 1, "b": [2, 3]}')
        assert load_raw_state(good) == {"a": 1, "b": [2, 3]}


class TestSaveRawState:
    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "state.json"
        save_raw_state({"k": "v"}, target)
        assert target.exists()

    def test_sets_updated_at(self, tmp_path):
        target = tmp_path / "state.json"
        save_raw_state({"k": "v"}, target)
        loaded = json.loads(target.read_text())
        assert "updated_at" in loaded
        assert loaded["k"] == "v"

    def test_round_trip_via_load(self, tmp_path):
        target = tmp_path / "state.json"
        save_raw_state({"data": [1, 2, 3]}, target)
        loaded = load_raw_state(target)
        assert loaded["data"] == [1, 2, 3]

    def test_save_is_atomic_no_tmp_leftover_on_success(self, tmp_path):
        target = tmp_path / "state.json"
        save_raw_state({"k": "v"}, target)
        assert not (target.parent / (target.name + ".tmp")).exists()

    def test_save_overwrite_preserves_old_on_write_failure(self, tmp_path, monkeypatch):
        """If write_text fails mid-save, the original file survives."""
        target = tmp_path / "state.json"
        save_raw_state({"first": 1}, target)
        original_contents = target.read_text()

        def boom(self, *args, **kwargs):
            raise OSError("disk full")

        # Force the .tmp write to fail
        from pathlib import Path as _Path
        monkeypatch.setattr(_Path, "write_text", boom)
        with pytest.raises(OSError):
            save_raw_state({"second": 2}, target)

        # Original content preserved
        assert target.read_text() == original_contents
