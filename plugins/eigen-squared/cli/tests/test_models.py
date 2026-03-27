"""Tests for data models — round-trip serialization and validation."""

import pytest

from cli.models import (
    Convergence,
    FindingsSummary,
    MainCommandState,
    DeepenCommandState,
    SwarmExecution,
    EpicPlan,
    PhaseState,
    PhaseReview,
    PipelineState,
    Recommendation,
)
from cli.state import create_initial_state, validate_state


class TestRoundTrip:
    """Every model survives to_dict → from_dict without data loss."""

    def test_convergence(self):
        c = Convergence(converged=True, decided_by="deepen_time_split",
                        decided_at="2026-01-01T00:00:00Z", reason="test")
        assert Convergence.from_dict(c.to_dict()) == c

    def test_findings_summary(self):
        f = FindingsSummary(high=3, medium=2, low=1)
        assert FindingsSummary.from_dict(f.to_dict()) == f

    def test_main_command_state(self):
        m = MainCommandState(
            status="completed", iteration=3, last_run_at="2026-01-01T00:00:00Z",
            output_paths={"report": "path/to/report.json"},
            feedback_consumed=True,
            convergence=Convergence(converged=True, decided_by="test"),
            phase_count=3,
        )
        assert MainCommandState.from_dict(m.to_dict()) == m

    def test_main_command_state_no_phase_count(self):
        m = MainCommandState(status="completed", iteration=1)
        d = m.to_dict()
        assert "phase_count" not in d
        m2 = MainCommandState.from_dict(d)
        assert m2.phase_count is None

    def test_deepen_command_state(self):
        d = DeepenCommandState(
            status="completed", iteration=2,
            feedback_path="path/to/feedback.json",
            findings_summary=FindingsSummary(high=1, medium=0, low=5),
        )
        assert DeepenCommandState.from_dict(d.to_dict()) == d

    def test_deepen_command_state_locked_skills(self):
        d = DeepenCommandState(
            status="completed", iteration=3,
            locked_skills=["skill-a", "skill-b", "skill-c"],
            findings_summary=FindingsSummary(high=0, medium=1, low=2),
        )
        serialized = d.to_dict()
        assert serialized["locked_skills"] == ["skill-a", "skill-b", "skill-c"]
        restored = DeepenCommandState.from_dict(serialized)
        assert restored == d
        assert restored.locked_skills == ["skill-a", "skill-b", "skill-c"]

    def test_deepen_command_state_no_locked_skills(self):
        d = DeepenCommandState(status="completed", iteration=1)
        serialized = d.to_dict()
        assert "locked_skills" not in serialized
        restored = DeepenCommandState.from_dict(serialized)
        assert restored.locked_skills is None

    def test_swarm_execution(self):
        s = SwarmExecution(
            status="pr_created", integration_branch="feat/P1.E2",
            pr_url="https://github.com/test/pull/42", pr_number=42,
            manifest_path="path/manifest.json", review_iteration=2,
            convergence=Convergence(converged=False),
            findings_summary={"p1": 1, "p2": 3, "p3": 0},
            review_reports=["report_1.md", "report_2.md"],
        )
        assert SwarmExecution.from_dict(s.to_dict()) == s

    def test_epic_plan(self):
        e = EpicPlan(
            plan_epic_converge=MainCommandState(status="completed", iteration=2),
            swarm_execution=SwarmExecution(status="pr_created"),
        )
        assert EpicPlan.from_dict(e.to_dict()) == e

    def test_phase_state(self):
        p = PhaseState(
            bootstrap=MainCommandState(status="completed"),
            plans={"1": EpicPlan(), "2": EpicPlan()},
        )
        d = p.to_dict()
        p2 = PhaseState.from_dict(d)
        assert p2.bootstrap.status == "completed"
        assert len(p2.plans) == 2

    def test_pipeline_state_full(self):
        state = create_initial_state("test-initiative", 3)
        d = state.to_dict()
        state2 = PipelineState.from_dict(d)
        d2 = state2.to_dict()
        assert d == d2

    def test_recommendation(self):
        r = Recommendation(from_cmd="deepen_time_split", at_iteration=2,
                           phase=1, epic=None, text="some observation")
        d = r.to_dict()
        r2 = Recommendation.from_dict(d)
        assert r2.from_cmd == "deepen_time_split"
        assert r2.text == "some observation"


class TestFromDictDefaults:
    """Missing keys in JSON get filled with sensible defaults."""

    def test_empty_dict(self):
        ps = PipelineState.from_dict({})
        assert ps.initiative == ""
        assert ps.time_split.status == "not_started"
        assert ps.phases == {}

    def test_none_input(self):
        ps = PipelineState.from_dict(None)
        assert ps.schema_version == "2.0.0"

    def test_convergence_none(self):
        c = Convergence.from_dict(None)
        assert c.converged is False

    def test_phase_with_missing_keys(self):
        p = PhaseState.from_dict({"space_split": {"status": "completed"}})
        assert p.space_split.status == "completed"
        assert p.bootstrap.status == "not_started"  # filled with default

    def test_swarm_execution_string_pr_number(self):
        s = SwarmExecution.from_dict({"pr_number": "42"})
        assert s.pr_number == 42

    def test_phase_count_as_string(self):
        m = MainCommandState.from_dict({"phase_count": "3"})
        assert m.phase_count == 3

    def test_phase_count_invalid_string(self):
        m = MainCommandState.from_dict({"phase_count": "abc"})
        assert m.phase_count is None


class TestValidation:

    def test_valid_initial_state(self):
        state = create_initial_state("test", 2)
        assert validate_state(state) == []

    def test_invalid_status(self):
        state = create_initial_state("test", 1)
        state.time_split.status = "bogus"
        errors = validate_state(state)
        assert len(errors) == 1
        assert "time_split.status" in errors[0]

    def test_invalid_phase_status(self):
        state = create_initial_state("test", 1)
        state.phases["1"].bootstrap.status = "running"
        errors = validate_state(state)
        assert len(errors) == 1
        assert "bootstrap.status" in errors[0]

    def test_invalid_swarm_status(self):
        state = create_initial_state("test", 1)
        state.phases["1"].plans["1"] = EpicPlan(
            swarm_execution=SwarmExecution(status="invalid")
        )
        errors = validate_state(state)
        assert any("swarm_execution.status" in e for e in errors)


class TestBackwardCompatibility:
    """CLI can load v1.x pipeline_state.json files."""

    def test_v1_state_with_root_bootstrap(self):
        """v1.x bug: bootstrap at state.bootstrap instead of state.phases.N.bootstrap."""
        v1 = {
            "initiative": "test",
            "state": {
                "time_split": {"status": "completed", "convergence": {"converged": True}, "phase_count": 1},
                "deepen_time_split": {"status": "completed"},
                "bootstrap": {"status": "not_started"},  # wrong level
                "phases": {
                    "1": {
                        "space_split": {"status": "not_started"},
                        "deepen_space_split": {"status": "not_started"},
                    }
                },
            },
        }
        ps = PipelineState.from_dict(v1)
        assert ps.time_split.convergence.converged is True
        assert ps.phases["1"].bootstrap.status == "not_started"  # default, not root
        assert ps.phases["1"].space_split.status == "not_started"

    def test_v1_state_missing_schema_version(self):
        v1 = {"initiative": "test", "state": {"time_split": {}, "deepen_time_split": {}}}
        ps = PipelineState.from_dict(v1)
        assert ps.schema_version == "1.0.0"  # preserved from input

    def test_epic_plan_ignores_unknown_keys(self):
        """EpicPlan.from_dict ignores unknown keys (e.g., old plan_phase_epic)."""
        d = {
            "plan_phase_epic": {"status": "completed"},  # unknown/old key
            "swarm_execution": {"status": "not_started"},
        }
        ep = EpicPlan.from_dict(d)
        # plan_epic_converge should be default (not_started), not migrated
        assert ep.plan_epic_converge.status == "not_started"
        assert ep.swarm_execution.status == "not_started"
