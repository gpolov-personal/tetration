"""TDD tests for lite pipeline state models.

Written before models_lite.py exists — these tests drive the schema shape.
"""

import pytest

from cli.models_lite import (
    LITE_STATE_RELATIVE_PATH,
    LiteConvergence,
    LiteEpicState,
    LitePipelineState,
    LitePlanState,
    LiteReviewState,
    LiteSwarmExecution,
    SquaredSchemaDetected,
)
from eigen_core.cli.base_models import Convergence, FindingsSummary


# ---------------------------------------------------------------------------
# LitePlanState
# ---------------------------------------------------------------------------

class TestLitePlanState:
    def test_default_values(self):
        s = LitePlanState()
        assert s.status == "not_started"
        assert s.iteration == 0
        assert s.stages_completed == []
        assert s.output_paths == {
            "phase_manifest": None,
            "bootstrap_report": None,
            "epic_manifest": None,
            "phase_e2e_config": None,
        }
        assert s.findings_summary == FindingsSummary()
        assert s.convergence == Convergence()

    def test_round_trip_default(self):
        s = LitePlanState()
        assert LitePlanState.from_dict(s.to_dict()) == s

    def test_round_trip_populated(self):
        s = LitePlanState(
            status="in_progress",
            iteration=2,
            stages_completed=["A", "B", "C", "E:1"],
            output_paths={
                "phase_manifest": "phases/phase_1/phase_1_manifest.md",
                "bootstrap_report": "phases/phase_1/bootstrap-report.json",
                "epic_manifest": "phases/phase_1/epic_manifest.json",
                "phase_e2e_config": "phases/phase_1/phase_e2e_config.json",
            },
            findings_summary=FindingsSummary(high=1, medium=2, low=3),
            convergence=Convergence(converged=True, decided_by="self", reason="done"),
        )
        assert LitePlanState.from_dict(s.to_dict()) == s

    def test_stages_completed_supports_per_epic_markers(self):
        """Stage E loops per epic — tracked as E:1, E:2, ... per plan §3.1."""
        s = LitePlanState(stages_completed=["A", "B", "C", "D", "E:1", "E:2"])
        round_tripped = LitePlanState.from_dict(s.to_dict())
        assert round_tripped.stages_completed == ["A", "B", "C", "D", "E:1", "E:2"]

    def test_from_none_returns_default(self):
        assert LitePlanState.from_dict(None) == LitePlanState()

    def test_from_empty_dict_returns_default(self):
        assert LitePlanState.from_dict({}) == LitePlanState()

    def test_partial_dict_fills_missing_fields(self):
        partial = {"status": "completed", "iteration": 5}
        s = LitePlanState.from_dict(partial)
        assert s.status == "completed"
        assert s.iteration == 5
        assert s.stages_completed == []
        assert s.convergence == Convergence()


# ---------------------------------------------------------------------------
# LiteSwarmExecution
# ---------------------------------------------------------------------------

class TestLiteSwarmExecution:
    def test_default_values(self):
        s = LiteSwarmExecution()
        assert s.status == "not_started"
        assert s.pr_url is None
        assert s.pr_number is None
        assert s.integration_branch is None
        assert s.convergence == Convergence()

    def test_round_trip_populated(self):
        s = LiteSwarmExecution(
            status="pr_created",
            pr_url="https://github.com/owner/repo/pull/42",
            pr_number=42,
            integration_branch="feat/P1.E1",
            convergence=Convergence(converged=False),
        )
        assert LiteSwarmExecution.from_dict(s.to_dict()) == s

    def test_pr_number_coerced_from_string(self):
        s = LiteSwarmExecution.from_dict({"pr_number": "17"})
        assert s.pr_number == 17

    def test_pr_number_garbage_becomes_none(self):
        s = LiteSwarmExecution.from_dict({"pr_number": "not-a-number"})
        assert s.pr_number is None

    def test_from_none_returns_default(self):
        assert LiteSwarmExecution.from_dict(None) == LiteSwarmExecution()


# ---------------------------------------------------------------------------
# LiteReviewState
# ---------------------------------------------------------------------------

class TestLiteReviewState:
    def test_default_values(self):
        r = LiteReviewState()
        assert r.status == "not_started"
        assert r.review_iteration == 0
        assert r.findings_summary == {"p1": 0, "p2": 0, "p3": 0}
        assert r.convergence == Convergence()
        assert r.review_reports == []

    def test_findings_summary_is_priority_shape_not_severity(self):
        """Lite uses p1/p2/p3 priorities (like squared's SwarmExecution),
        not high/medium/low severities (like LitePlanState).
        """
        r = LiteReviewState(findings_summary={"p1": 3, "p2": 5, "p3": 1})
        round_tripped = LiteReviewState.from_dict(r.to_dict())
        assert round_tripped.findings_summary == {"p1": 3, "p2": 5, "p3": 1}

    def test_round_trip_populated(self):
        r = LiteReviewState(
            status="in_progress",
            review_iteration=2,
            findings_summary={"p1": 1, "p2": 0, "p3": 4},
            convergence=Convergence(converged=True, reason="P1=0 AND P2=0"),
            review_reports=["review-1.md", "review-2.md"],
        )
        assert LiteReviewState.from_dict(r.to_dict()) == r

    def test_from_none_returns_default(self):
        assert LiteReviewState.from_dict(None) == LiteReviewState()


# ---------------------------------------------------------------------------
# LiteEpicState
# ---------------------------------------------------------------------------

class TestLiteEpicState:
    def test_default_values(self):
        e = LiteEpicState()
        assert e.epic_path is None
        assert e.epic_file is None
        assert e.plan_file is None
        assert e.swarm_manifest is None
        assert e.is_e2e_epic is False
        assert e.lite_swarm == LiteSwarmExecution()
        assert e.lite_review == LiteReviewState()

    def test_round_trip_feature_epic(self):
        e = LiteEpicState(
            epic_path="phases/phase_1/epic_1/",
            epic_file="phases/phase_1/epic_1/epic.md",
            plan_file="phases/phase_1/epic_1/plan.md",
            swarm_manifest="phases/phase_1/epic_1/swarm-manifest.json",
            is_e2e_epic=False,
            lite_swarm=LiteSwarmExecution(
                status="pr_created", pr_number=10,
                integration_branch="feat/P1.E1",
            ),
            lite_review=LiteReviewState(review_iteration=1),
        )
        assert LiteEpicState.from_dict(e.to_dict()) == e

    def test_round_trip_e2e_epic(self):
        e = LiteEpicState(
            epic_path="phases/phase_1/epic_3/",
            epic_file="phases/phase_1/epic_3/epic.md",
            is_e2e_epic=True,
        )
        round_tripped = LiteEpicState.from_dict(e.to_dict())
        assert round_tripped.is_e2e_epic is True

    def test_from_none_returns_default(self):
        assert LiteEpicState.from_dict(None) == LiteEpicState()


# ---------------------------------------------------------------------------
# LitePipelineState (root)
# ---------------------------------------------------------------------------

class TestLitePipelineState:
    def test_default_values(self):
        s = LitePipelineState()
        assert s.schema_version == "1.0.0"
        assert s.feature_set == ""
        assert s.phase == 1  # always 1 in lite
        assert s.epic_count == 0
        assert s.lite_plan == LitePlanState()
        assert s.epics == {}
        assert s.recommendations == []

    def test_round_trip_minimal(self):
        s = LitePipelineState(
            feature_set="my-initiative",
            epic_count=0,
        )
        assert LitePipelineState.from_dict(s.to_dict()) == s

    def test_round_trip_with_epics(self):
        s = LitePipelineState(
            feature_set="my-initiative",
            epic_count=3,
            lite_plan=LitePlanState(
                status="completed",
                stages_completed=["A", "B", "C", "D", "E:1", "E:2", "E:3"],
                convergence=Convergence(converged=True),
            ),
            epics={
                "1": LiteEpicState(
                    epic_path="phases/phase_1/epic_1/",
                    lite_swarm=LiteSwarmExecution(
                        integration_branch="feat/P1.E1",
                    ),
                ),
                "2": LiteEpicState(
                    epic_path="phases/phase_1/epic_2/",
                    lite_swarm=LiteSwarmExecution(
                        integration_branch="feat/P1.E2",
                    ),
                ),
                "3": LiteEpicState(
                    epic_path="phases/phase_1/epic_3/",
                    is_e2e_epic=True,
                    lite_swarm=LiteSwarmExecution(
                        integration_branch="feat/P1.E3",
                    ),
                ),
            },
        )
        assert LitePipelineState.from_dict(s.to_dict()) == s

    def test_to_dict_nests_state_key(self):
        """Matches squared's convention: raw dict has a top-level 'state' key."""
        s = LitePipelineState(feature_set="x", epic_count=1)
        d = s.to_dict()
        assert "state" in d
        assert "lite_plan" in d["state"]
        assert "epics" in d["state"]
        assert d["schema_version"] == "1.0.0"
        assert d["feature_set"] == "x"

    def test_from_none_returns_default(self):
        assert LitePipelineState.from_dict(None) == LitePipelineState()

    def test_from_empty_dict_returns_default(self):
        assert LitePipelineState.from_dict({}) == LitePipelineState()

    def test_recommendations_preserved_as_list(self):
        """Lite simplifies recommendations to a flat list (vs squared's per-command dict)."""
        s = LitePipelineState(
            feature_set="x",
            recommendations=[{"from": "lite_plan", "text": "revisit"}],
        )
        round_tripped = LitePipelineState.from_dict(s.to_dict())
        assert round_tripped.recommendations == [{"from": "lite_plan", "text": "revisit"}]

    def test_epic_count_garbage_becomes_zero(self):
        s = LitePipelineState.from_dict({"epic_count": "not-a-number"})
        assert s.epic_count == 0


# ---------------------------------------------------------------------------
# H1 — Schema-collision guard: refuse to parse squared's state shape
# ---------------------------------------------------------------------------

class TestSquaredSchemaGuard:
    def test_rejects_schema_version_2x(self):
        raw = {"schema_version": "2.0.0", "state": {}}
        with pytest.raises(SquaredSchemaDetected):
            LitePipelineState.from_dict(raw)

    def test_rejects_state_with_time_split(self):
        raw = {"schema_version": "1.0.0", "state": {"time_split": {"status": "completed"}}}
        with pytest.raises(SquaredSchemaDetected):
            LitePipelineState.from_dict(raw)

    def test_rejects_state_with_phases_dict(self):
        raw = {"schema_version": "1.0.0", "state": {"phases": {"1": {}}}}
        with pytest.raises(SquaredSchemaDetected):
            LitePipelineState.from_dict(raw)

    def test_lite_relative_path_distinct_from_squared(self):
        """Lite writes to a path that will never be confused with squared's."""
        assert LITE_STATE_RELATIVE_PATH != "eigen_initiative/phases/pipeline_state.json"
        assert "lite" in LITE_STATE_RELATIVE_PATH


# ---------------------------------------------------------------------------
# LiteConvergence alias (plan §8 Sprint 2 point 3)
# ---------------------------------------------------------------------------

class TestLiteConvergenceAlias:
    def test_alias_points_to_core_convergence(self):
        assert LiteConvergence is Convergence
