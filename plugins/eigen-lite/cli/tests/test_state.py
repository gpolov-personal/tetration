"""Tests for state.py — typed I/O + validate_state_lite invariants."""

import json

import pytest

from cli.models_lite import (
    LiteConvergence,
    LiteEpicState,
    LitePipelineState,
    LitePlanState,
    LiteReviewState,
    LiteSwarmExecution,
    SquaredSchemaDetected,
)
from cli.state import (
    create_initial_state,
    load_state,
    resolve_state_file,
    save_state,
    validate_state_lite,
)
from eigen_core.cli.state_io import CorruptStateFile


# ---------------------------------------------------------------------------
# resolve_state_file
# ---------------------------------------------------------------------------

class TestResolveStateFile:
    def test_points_to_lite_specific_filename(self, tmp_path):
        resolved = resolve_state_file(tmp_path)
        assert resolved.name == "pipeline_state_lite.json"
        assert resolved.parent.name == "phases"


# ---------------------------------------------------------------------------
# Round trip: create → save → load
# ---------------------------------------------------------------------------

class TestCreateSaveLoad:
    def test_create_initial_state_sets_fields(self):
        s = create_initial_state("my-init", epic_count=3)
        assert s.feature_set == "my-init"
        assert s.epic_count == 3
        assert s.created_at is not None
        assert s.updated_at is not None

    def test_save_then_load_roundtrip(self, tmp_path):
        state_file = tmp_path / "state.json"
        original = create_initial_state("x", epic_count=0)
        save_state(original, state_file)
        loaded = load_state(state_file)
        assert loaded is not None
        assert loaded.feature_set == "x"

    def test_load_missing_returns_none(self, tmp_path):
        assert load_state(tmp_path / "no.json") is None

    def test_load_corrupt_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json {")
        with pytest.raises(CorruptStateFile):
            load_state(bad)

    def test_load_squared_schema_raises(self, tmp_path):
        """H1 guard: reject squared's state shape rather than silently
        convert it into an empty lite state and overwrite on next save.
        """
        squared_shape = tmp_path / "state.json"
        squared_shape.write_text(json.dumps({
            "schema_version": "2.0.0",
            "state": {"time_split": {}, "phases": {}},
        }))
        with pytest.raises(SquaredSchemaDetected):
            load_state(squared_shape)


# ---------------------------------------------------------------------------
# validate_state_lite — invariants
# ---------------------------------------------------------------------------

def _healthy_epic(num: int, is_e2e: bool = False) -> LiteEpicState:
    return LiteEpicState(
        epic_path=f"phases/phase_1/epic_{num}/",
        epic_file=f"phases/phase_1/epic_{num}/epic.md",
        is_e2e_epic=is_e2e,
        lite_swarm=LiteSwarmExecution(integration_branch=f"feat/P1.E{num}"),
        lite_review=LiteReviewState(),
    )


class TestValidateHappyPath:
    def test_fresh_state_valid(self):
        assert validate_state_lite(create_initial_state("x")) == []

    def test_populated_state_valid(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=2,
            epics={
                "1": _healthy_epic(1),
                "2": _healthy_epic(2, is_e2e=True),
            },
        )
        assert validate_state_lite(s) == []

    def test_plan_converged_with_all_stage_markers_valid(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=2,
            lite_plan=LitePlanState(
                status="completed",
                stages_completed=["A", "B", "C", "D", "E:1", "E:2"],
                convergence=LiteConvergence(converged=True),
            ),
            epics={"1": _healthy_epic(1), "2": _healthy_epic(2, is_e2e=True)},
        )
        assert validate_state_lite(s) == []


class TestValidateStructuralInvariants:
    def test_epic_count_mismatch_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=3,  # mismatch — epics dict only has 1
            epics={"1": _healthy_epic(1)},
        )
        errors = validate_state_lite(s)
        assert any("epic_count" in e and "!=" in e for e in errors)

    def test_non_contiguous_epic_keys_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=2,
            epics={"1": _healthy_epic(1), "3": _healthy_epic(3)},
        )
        errors = validate_state_lite(s)
        assert any("contiguous" in e for e in errors)

    def test_non_integer_epic_key_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epics={"abc": _healthy_epic(1)},
        )
        errors = validate_state_lite(s)
        assert any("non-integer" in e for e in errors)

    def test_multiple_e2e_epics_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=2,
            epics={
                "1": _healthy_epic(1, is_e2e=True),
                "2": _healthy_epic(2, is_e2e=True),
            },
        )
        errors = validate_state_lite(s)
        assert any("multiple epics marked is_e2e_epic" in e for e in errors)

    def test_e2e_epic_must_be_last_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=2,
            epics={
                "1": _healthy_epic(1, is_e2e=True),
                "2": _healthy_epic(2),
            },
        )
        errors = validate_state_lite(s)
        assert any("last epic" in e for e in errors)


class TestValidateSwarmConvergenceCoherence:
    def test_status_converged_without_flag_flagged(self):
        epic = _healthy_epic(1)
        epic.lite_swarm = LiteSwarmExecution(
            status="converged",
            integration_branch="feat/P1.E1",
            convergence=LiteConvergence(converged=False),
        )
        s = LitePipelineState(feature_set="x", epic_count=1, epics={"1": epic})
        errors = validate_state_lite(s)
        assert any("status='converged'" in e for e in errors)


class TestValidateIntegrationBranch:
    def test_wrong_branch_shape_flagged(self):
        epic = _healthy_epic(1)
        epic.lite_swarm = LiteSwarmExecution(integration_branch="feat/wrong")
        s = LitePipelineState(feature_set="x", epic_count=1, epics={"1": epic})
        errors = validate_state_lite(s)
        assert any("integration_branch" in e for e in errors)


class TestValidateStagesCompleted:
    def test_unknown_marker_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=1,
            lite_plan=LitePlanState(stages_completed=["A", "Z"]),
            epics={"1": _healthy_epic(1)},
        )
        errors = validate_state_lite(s)
        assert any("unknown marker" in e for e in errors)

    def test_e_marker_beyond_epic_count_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=1,
            lite_plan=LitePlanState(stages_completed=["A", "B", "C", "D", "E:1", "E:2"]),
            epics={"1": _healthy_epic(1)},
        )
        errors = validate_state_lite(s)
        assert any("unknown marker" in e and "E:2" in e for e in errors)

    def test_plan_converged_without_all_markers_flagged(self):
        s = LitePipelineState(
            feature_set="x",
            epic_count=3,
            lite_plan=LitePlanState(
                stages_completed=["A", "B", "C", "D", "E:1"],  # missing E:2, E:3
                convergence=LiteConvergence(converged=True),
            ),
            epics={
                "1": _healthy_epic(1),
                "2": _healthy_epic(2),
                "3": _healthy_epic(3, is_e2e=True),
            },
        )
        errors = validate_state_lite(s)
        assert any("missing stage markers" in e for e in errors)
        assert any("E:2" in e for e in errors)
