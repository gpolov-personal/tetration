"""Phase-slot support: state round-trip + next-context carry the phase number,
so a single-phase run can slot as phase 2 onto a repo that already ran phase 1."""

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from cli.state_small import SmallPipelineState, create_initial_state  # noqa: E402
from cli.transitions_small import determine_next_small  # noqa: E402


def test_phase_defaults_to_1() -> None:
    assert create_initial_state("x").phase == 1


def test_phase_set_and_round_trips() -> None:
    s = create_initial_state("x", phase=2)
    assert s.phase == 2
    assert SmallPipelineState.from_dict(s.to_dict()).phase == 2


def test_phase_carried_in_plan_context() -> None:
    s = create_initial_state("x", phase=2)
    s.shape = "single_phase"
    cmd, ctx = determine_next_small(s.to_dict())
    assert cmd == "small_plan"
    assert ctx["phase"] == 2


def test_phase_carried_in_build_context() -> None:
    s = create_initial_state("x", phase=2)
    s.shape = "single_phase"
    for stage in s.stages.values():
        stage.status = "done"
    raw = s.to_dict()
    raw["waves"] = [{"id": "a", "epics": ["E1"], "goal_status": {"E1": "pending"}, "review_status": "pending"}]
    cmd, ctx = determine_next_small(raw)
    assert cmd == "small_build"
    assert ctx["phase"] == 2
