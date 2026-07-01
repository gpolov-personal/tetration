"""Persisted goal-attempt counter (the circuit-breaker that survives a resume):
model round-trip + `record-goal-attempt` increment/reset via the CLI, and that
`set-waves` initializes the counter to 0 per epic."""

import json
import os
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from cli.main import main  # noqa: E402
from cli.state_small import Wave, create_initial_state, load_state, save_state  # noqa: E402


def _load(path: str):
    """Load state, asserting it is present (narrows Optional for the type checker)."""
    st = load_state(path)
    assert st is not None
    return st


def test_goal_attempts_round_trip() -> None:
    w = Wave(id="a", epics=["E1"], goal_attempts={"E1": 3})
    assert Wave.from_dict(w.to_dict()).goal_attempts == {"E1": 3}


def test_set_waves_initializes_counter() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "state.json")
        assert main(["--state-file", p, "init", "--initiative", "x"]) == 0
        assert main(["--state-file", p, "set-waves", "--waves",
                     json.dumps([{"id": "a", "epics": ["E1", "E2"], "parallel": True}])]) == 0
        assert _load(p).waves[0].goal_attempts == {"E1": 0, "E2": 0}


def test_record_goal_attempt_increment_and_reset() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "state.json")
        st = create_initial_state("x")
        st.waves = [Wave(id="a", epics=["E1"], goal_status={"E1": "pending"},
                         goal_attempts={"E1": 0})]
        save_state(st, p)

        assert main(["--state-file", p, "record-goal-attempt", "a", "E1"]) == 0
        assert _load(p).waves[0].goal_attempts["E1"] == 1
        main(["--state-file", p, "record-goal-attempt", "a", "E1"])
        assert _load(p).waves[0].goal_attempts["E1"] == 2      # persists across calls (survives a resume)
        main(["--state-file", p, "record-goal-attempt", "a", "E1", "--reset"])
        assert _load(p).waves[0].goal_attempts["E1"] == 0      # human grants a fresh N


def test_record_goal_attempt_rejects_unknown_epic() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "state.json")
        st = create_initial_state("x")
        st.waves = [Wave(id="a", epics=["E1"], goal_attempts={"E1": 0})]
        save_state(st, p)
        assert main(["--state-file", p, "record-goal-attempt", "a", "E9"]) == 1  # not in wave
