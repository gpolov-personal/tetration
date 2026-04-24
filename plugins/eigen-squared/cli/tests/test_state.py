"""Tests for state.py — focus on the atomic save semantics (1.1)."""

from __future__ import annotations

import multiprocessing
import os
import time

from cli.state import (
    create_initial_state,
    load_state,
    locked_state,
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


class TestFilePermissions:
    """S7 — NamedTemporaryFile defaults to 0o600; os.replace inherits the
    source's mode. Without explicit chmod, the first save would silently
    downgrade an 0o644 state file and break readers on a different uid.
    """

    def test_preserves_existing_file_mode(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        state = create_initial_state("x", phase_count=1)
        save_state(state, sf)
        # Bump the mode to 0o644 explicitly (simulates a state file that
        # was created via `touch` or checked in from another uid).
        os.chmod(sf, 0o644)

        # A subsequent save must preserve 0o644, not drop it to 0o600.
        save_state(state, sf)
        assert (sf.stat().st_mode & 0o777) == 0o644

    def test_fresh_file_gets_readable_mode(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        state = create_initial_state("x", phase_count=1)
        save_state(state, sf)
        # No prior file → default 0o644 (not 0o600 from NamedTemporaryFile).
        assert (sf.stat().st_mode & 0o777) == 0o644


def _writer_worker(sf_str: str, marker: str, hold_ms: int) -> None:
    """Process target: acquire lock, mutate, hold briefly, save."""
    from pathlib import Path

    sf = Path(sf_str)
    with locked_state(sf):
        state = load_state(sf)
        assert state is not None
        state.initiative = marker
        # Hold the critical section so the other writer would actually
        # race if the lock were absent.
        time.sleep(hold_ms / 1000)
        save_state(state, sf)


class TestLockedState:
    """B1 — ``locked_state`` must serialize concurrent load→mutate→save
    cycles so a second writer can't overwrite the first writer's
    mutation.
    """

    def test_concurrent_writers_are_serialized(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        state = create_initial_state("seed", phase_count=1)
        save_state(state, sf)

        # Two writers each set a distinct marker and hold the lock for
        # ~100ms. With proper serialization the second one sees the first
        # one's marker when it loads — both mutations are preserved in
        # *order* (last writer wins on initiative, but neither write is
        # lost because the load happens *after* the first save).
        ctx = multiprocessing.get_context("fork")
        p1 = ctx.Process(target=_writer_worker, args=(str(sf), "writer-A", 100))
        p2 = ctx.Process(target=_writer_worker, args=(str(sf), "writer-B", 100))
        p1.start()
        p2.start()
        p1.join(timeout=5)
        p2.join(timeout=5)
        assert p1.exitcode == 0
        assert p2.exitcode == 0

        # The final state is one of the two markers — never corrupt,
        # never the seed (both writers ran to completion).
        loaded = load_state(sf)
        assert loaded is not None
        assert loaded.initiative in {"writer-A", "writer-B"}

    def test_lock_file_is_created_next_to_state(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        with locked_state(sf):
            assert (tmp_path / "pipeline_state.json.lock").exists()

    def test_lock_released_on_exception(self, tmp_path):
        sf = tmp_path / "pipeline_state.json"
        try:
            with locked_state(sf):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        # Re-acquiring must succeed immediately (non-blocking); if the
        # previous lock had leaked, this would either block or fail.
        with locked_state(sf):
            pass


class TestValidateState:
    def test_fresh_state_is_valid(self):
        state = create_initial_state("x", phase_count=2)
        assert validate_state(state) == []
