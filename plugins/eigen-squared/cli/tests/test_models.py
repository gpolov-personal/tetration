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

    def test_swarm_execution_findings_history(self):
        s = SwarmExecution(
            status="iterating", review_iteration=2,
            findings_summary={"p1": 1, "p2": 0, "p3": 19},
            findings_history=[
                {"iteration": 0, "p1": 1, "p2": 6, "p3": 14,
                 "signatures": ["sha1aaa", "sha1bbb"]},
                {"iteration": 1, "p1": 1, "p2": 0, "p3": 19,
                 "signatures": ["sha1bbb", "sha1ccc"]},
            ],
        )
        d = s.to_dict()
        assert "findings_history" in d
        assert len(d["findings_history"]) == 2
        assert d["findings_history"][0]["signatures"] == ["sha1aaa", "sha1bbb"]
        assert SwarmExecution.from_dict(d) == s

    def test_swarm_execution_findings_history_default_empty(self):
        s = SwarmExecution()
        assert s.findings_history == []
        assert SwarmExecution.from_dict({}).findings_history == []

    def test_epic_plan(self):
        e = EpicPlan(
            plan_epic_converge=MainCommandState(status="completed", iteration=2),
            swarm_execution=SwarmExecution(status="pr_created"),
        )
        assert EpicPlan.from_dict(e.to_dict()) == e

    def test_phase_state(self):
        p = PhaseState(
            bootstrap_converge=MainCommandState(status="completed"),
            plans={"1": EpicPlan(), "2": EpicPlan()},
        )
        d = p.to_dict()
        p2 = PhaseState.from_dict(d)
        assert p2.bootstrap_converge.status == "completed"
        assert len(p2.plans) == 2

    def test_main_command_state_locked_skills(self):
        m = MainCommandState(
            status="completed", iteration=2,
            locked_skills=["skill-a", "skill-b"],
            findings_summary=FindingsSummary(high=0, medium=1, low=2),
        )
        d = m.to_dict()
        assert d["locked_skills"] == ["skill-a", "skill-b"]
        m2 = MainCommandState.from_dict(d)
        assert m2 == m

    def test_main_command_state_no_locked_skills(self):
        m = MainCommandState(status="completed", iteration=1)
        d = m.to_dict()
        assert "locked_skills" not in d
        m2 = MainCommandState.from_dict(d)
        assert m2.locked_skills is None

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
        p = PhaseState.from_dict({"space_split_converge": {"status": "completed"}})
        assert p.space_split_converge.status == "completed"
        assert p.bootstrap_converge.status == "not_started"  # filled with default

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
        state.phases["1"].bootstrap_converge.status = "running"
        errors = validate_state(state)
        assert len(errors) == 1
        assert "bootstrap_converge.status" in errors[0]

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
        """v1.x bug: bootstrap at state.bootstrap instead of state.phases.N."""
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
        assert ps.phases["1"].bootstrap_converge.status == "not_started"  # default, not root
        # legacy space_split + deepen_space_split pair migrates to space_split_converge
        assert ps.phases["1"].space_split_converge.status == "not_started"

    def test_v2_to_v3_bootstrap_pair_migrates_to_converge(self):
        """v2 → v3 migration: legacy bootstrap + deepen_bootstrap pair fuses into bootstrap_converge."""
        v2 = {
            "bootstrap": {
                "status": "completed",
                "iteration": 2,
                "output_paths": {"bootstrap_report": "phases/phase_1/bootstrap-report.json"},
                "convergence": {"converged": False},
                "feedback_consumed": True,
            },
            "deepen_bootstrap": {
                "status": "completed",
                "iteration": 2,
                "feedback_path": "phases/phase_1/feedback/deepen_bootstrap_feedback.json",
                "findings_summary": {"high": 0, "medium": 1, "low": 3},
                "locked_skills": ["python-testing-patterns", "language-profiles"],
            },
            "space_split": {"status": "not_started"},
            "deepen_space_split": {"status": "not_started"},
        }
        ph = PhaseState.from_dict(v2)
        # bootstrap_converge inherits status, iteration, output_paths from main
        assert ph.bootstrap_converge.status == "completed"
        assert ph.bootstrap_converge.iteration == 2
        assert ph.bootstrap_converge.output_paths["bootstrap_report"] == "phases/phase_1/bootstrap-report.json"
        # findings_summary promoted from deepen
        assert ph.bootstrap_converge.findings_summary is not None
        assert ph.bootstrap_converge.findings_summary.medium == 1
        # locked_skills promoted from deepen
        assert ph.bootstrap_converge.locked_skills == ["python-testing-patterns", "language-profiles"]
        # feedback_path stashed in output_paths["feedback_file"]
        assert ph.bootstrap_converge.output_paths["feedback_file"] == "phases/phase_1/feedback/deepen_bootstrap_feedback.json"

    def test_v3_to_v4_space_split_pair_migrates_to_converge(self):
        """v3 → v4 migration: legacy space_split + deepen_space_split pair fuses into space_split_converge."""
        v3 = {
            "bootstrap_converge": {"status": "completed", "convergence": {"converged": True}},
            "space_split": {
                "status": "completed",
                "iteration": 3,
                "output_paths": {
                    "epic_manifest": "phases/phase_1/epic_manifest.json",
                    "phase_e2e_config": "phases/phase_1/phase_e2e_config.json",
                },
                "convergence": {"converged": False},
                "feedback_consumed": True,
            },
            "deepen_space_split": {
                "status": "completed",
                "iteration": 3,
                "feedback_path": "phases/phase_1/feedback/deepen_space_split_feedback.json",
                "findings_summary": {"high": 0, "medium": 2, "low": 5},
                "locked_skills": ["api-design", "testing-patterns"],
            },
        }
        ph = PhaseState.from_dict(v3)
        # space_split_converge inherits status, iteration, output_paths from main
        assert ph.space_split_converge.status == "completed"
        assert ph.space_split_converge.iteration == 3
        assert ph.space_split_converge.output_paths["epic_manifest"] == "phases/phase_1/epic_manifest.json"
        assert ph.space_split_converge.output_paths["phase_e2e_config"] == "phases/phase_1/phase_e2e_config.json"
        # findings_summary promoted from deepen
        assert ph.space_split_converge.findings_summary is not None
        assert ph.space_split_converge.findings_summary.medium == 2
        assert ph.space_split_converge.findings_summary.low == 5
        # locked_skills promoted from deepen
        assert ph.space_split_converge.locked_skills == ["api-design", "testing-patterns"]
        # feedback_path stashed in output_paths["feedback_file"]
        assert ph.space_split_converge.output_paths["feedback_file"] == "phases/phase_1/feedback/deepen_space_split_feedback.json"

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
