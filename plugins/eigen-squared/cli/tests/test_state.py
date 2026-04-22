"""Tests for state.py — focus on the atomic save semantics (1.1)."""

from __future__ import annotations

import os

from cli.state import (
    create_initial_state,
    load_state,
    resolve_state_file,
    save_state,
    validate_state,
)


class TestResolveStateFile:
    def test_builds_canonical_path(self, tmp_path):
        assert (
            resolve_state_file(str(tmp_path))
            == tmp_path / "eigen_initiative" / "phases" / "pipeline_state.json"
        )


class TestSaveLoadRoundtrip:
    def test_write_then_read(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        state = create_initial_state("my initiative", phase_count=2)
        save_state(state, sf)
        assert sf.exists()

        loaded = load_state(sf)
        assert loaded is not None
        assert loaded.initiative == "my initiative"
        assert len(loaded.phases) == 2

    def test_overwrites_existing(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        state_a = create_initial_state("first", phase_count=1)
        save_state(state_a, sf)
        state_b = create_initial_state("second", phase_count=3)
        save_state(state_b, sf)

        loaded = load_state(sf)
        assert loaded is not None
        assert loaded.initiative == "second"
        assert len(loaded.phases) == 3


class TestAtomicWrite:
    """1.1 — save_state must write via tempfile + os.replace so a crash
    mid-write cannot leave the target file truncated.
    """

    def test_no_leftover_tempfile_after_success(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        state = create_initial_state("x", phase_count=1)
        save_state(state, sf)

        # Directory should contain exactly pipeline_state.json — no
        # stray .tmp siblings from the NamedTemporaryFile.
        entries = sorted(p.name for p in tmp_path.iterdir())
        assert entries == ["pipeline_state.json"]

    def test_previous_content_preserved_on_rename_failure(
        self, tmp_path, monkeypatch
    ):
        """If os.replace raises, the previously-saved file must remain
        readable; the caller receives the exception; no half-written
        content leaks through.
        """
        sf = tmp_path / "pipeline_state.json"
        original = create_initial_state("original", phase_count=1)
        save_state(original, sf)

        # Arrange the next save_state to fail at the rename step.
        def _boom(src, dst):
            raise OSError("simulated atomic rename failure")

        monkeypatch.setattr(os, "replace", _boom)

        replacement = create_initial_state("replacement", phase_count=5)
        try:
            save_state(replacement, sf)
        except OSError:
            pass  # expected

        # The original content must still be there and readable.
        loaded = load_state(sf)
        assert loaded is not None
        assert loaded.initiative == "original"
        assert len(loaded.phases) == 1

        # And the temp file must have been cleaned up.
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "pipeline_state.json"]
        assert leftovers == []

    def test_parent_dir_is_created(self, tmp_path):
        sf = tmp_path / "nested" / "deeper" / "pipeline_state.json"
        state = create_initial_state("nested", phase_count=1)
        save_state(state, sf)
        assert sf.exists()


class TestValidateState:
    def test_fresh_state_is_valid(self):
        state = create_initial_state("x", phase_count=2)
        assert validate_state(state) == []
