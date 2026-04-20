"""Tests for core subcommand handlers (Batch B)."""

import json
from argparse import Namespace

import pytest

from cli.state import load_state, resolve_state_file, save_state, create_initial_state
from cli.models_lite import (
    LiteConvergence,
    LiteEpicState,
    LitePipelineState,
    LiteReviewState,
    LiteSwarmExecution,
)
from cli.subcommands import (
    cmd_add_review_report,
    cmd_complete,
    cmd_get_context,
    cmd_init,
    cmd_init_epics,
    cmd_mark_converged,
    cmd_next,
    cmd_set_swarm_status,
    cmd_status,
    cmd_validate,
    dispatch,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def eigen_root(tmp_path, monkeypatch):
    monkeypatch.setenv("EIGEN_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def initialized_state(eigen_root):
    """Pipeline with lite_plan converged and 2 epics ready."""
    path = resolve_state_file(eigen_root)
    s = create_initial_state("my-init", epic_count=2)
    s.lite_plan.convergence = LiteConvergence(converged=True, decided_by="lite_plan")
    s.lite_plan.status = "completed"
    s.lite_plan.stages_completed = ["A", "B", "C", "D", "E:1", "E:2"]
    s.epics = {
        "1": LiteEpicState(
            epic_path="phases/phase_1/epic_1/",
            epic_file="phases/phase_1/epic_1/epic.md",
            plan_file="phases/phase_1/epic_1/plan.md",
            swarm_manifest="phases/phase_1/epic_1/swarm-manifest.json",
            lite_swarm=LiteSwarmExecution(integration_branch="feat/P1.E1"),
        ),
        "2": LiteEpicState(
            epic_path="phases/phase_1/epic_2/",
            epic_file="phases/phase_1/epic_2/epic.md",
            is_e2e_epic=True,
            lite_swarm=LiteSwarmExecution(integration_branch="feat/P1.E2"),
        ),
    }
    save_state(s, path)
    return path


def _ns(**kwargs) -> Namespace:
    return Namespace(**kwargs)


# ---------------------------------------------------------------------------
# cmd_init
# ---------------------------------------------------------------------------

class TestCmdInit:
    def test_creates_state_file(self, eigen_root, capsys):
        exit_code = cmd_init(_ns(
            feature_set="test", epic_count=0, state_file=None, force=False,
        ))
        assert exit_code == 0
        path = resolve_state_file(eigen_root)
        assert path.exists()
        state = load_state(path)
        assert state.feature_set == "test"

    def test_refuses_overwrite_without_force(self, eigen_root, capsys):
        cmd_init(_ns(feature_set="a", epic_count=0, state_file=None, force=False))
        exit_code = cmd_init(_ns(feature_set="b", epic_count=0, state_file=None,
                                 force=False))
        assert exit_code == 1

    def test_force_overwrites(self, eigen_root):
        cmd_init(_ns(feature_set="a", epic_count=0, state_file=None, force=False))
        exit_code = cmd_init(_ns(feature_set="b", epic_count=0, state_file=None,
                                 force=True))
        assert exit_code == 0
        state = load_state(resolve_state_file(eigen_root))
        assert state.feature_set == "b"


# ---------------------------------------------------------------------------
# cmd_status / cmd_next / cmd_validate
# ---------------------------------------------------------------------------

class TestCmdStatus:
    def test_json_output(self, initialized_state, capsys):
        cmd_status(_ns(state_file=str(initialized_state), as_json=True))
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["feature_set"] == "my-init"
        assert parsed["plan"]["converged"] is True
        assert set(parsed["epics"].keys()) == {"1", "2"}


class TestCmdNext:
    def test_returns_next_command(self, initialized_state, capsys):
        cmd_next(_ns(state_file=str(initialized_state), as_json=True))
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "ready"
        assert out["command"] == "lite_swarm"
        assert out["context"]["epic"] == 1

    def test_complete_when_all_converged(self, eigen_root, capsys):
        path = resolve_state_file(eigen_root)
        s = create_initial_state("x")
        s.lite_plan.convergence = LiteConvergence(converged=True)
        save_state(s, path)
        cmd_next(_ns(state_file=str(path), as_json=True))
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "complete"


class TestCmdValidate:
    def test_healthy_state_returns_zero(self, initialized_state, capsys):
        exit_code = cmd_validate(_ns(state_file=str(initialized_state)))
        assert exit_code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["valid"] is True

    def test_broken_state_returns_nonzero(self, eigen_root, capsys):
        path = resolve_state_file(eigen_root)
        s = create_initial_state("x", epic_count=5)  # claims 5, has 0 epics
        save_state(s, path)
        exit_code = cmd_validate(_ns(state_file=str(path)))
        assert exit_code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["valid"] is False
        assert any("epic_count" in e for e in out["errors"])


# ---------------------------------------------------------------------------
# cmd_get_context
# ---------------------------------------------------------------------------

class TestCmdGetContext:
    def test_lite_plan_context(self, initialized_state, capsys):
        cmd_get_context(_ns(
            state_file=str(initialized_state),
            target_command="lite_plan",
            epic=None,
        ))
        ctx = json.loads(capsys.readouterr().out)
        assert ctx["command"] == "lite_plan"
        assert ctx["scope"] == "initiative"
        assert ctx["feature_set"] == "my-init"
        # Fields consumed by lite_plan.md "On Entry":
        assert "stages_completed" in ctx
        assert "output_paths" in ctx
        assert "iteration" in ctx
        # Fixture has stages A-D and E:1, E:2 pre-populated via stages_completed
        assert set(ctx["stages_completed"]) >= {"A", "B", "C", "D"}

    def test_lite_swarm_context_requires_epic(self, initialized_state, capsys):
        exit_code = cmd_get_context(_ns(
            state_file=str(initialized_state),
            target_command="lite_swarm",
            epic=None,
        ))
        assert exit_code == 1

    def test_lite_swarm_context_returns_epic_metadata(self, initialized_state, capsys):
        cmd_get_context(_ns(
            state_file=str(initialized_state),
            target_command="lite_swarm",
            epic=1,
        ))
        ctx = json.loads(capsys.readouterr().out)
        assert ctx["command"] == "lite_swarm"
        assert ctx["epic"] == 1
        assert ctx["branch"] == "feat/P1.E1"
        assert ctx["manifest_path"] == "phases/phase_1/epic_1/swarm-manifest.json"
        # Swarm needs to know iteration/PR state for fixup-vs-fresh detection
        assert ctx["swarm_status"] == "not_started"
        assert ctx["review_iteration"] == 0
        assert ctx["pr_number"] is None
        assert ctx["pr_url"] is None

    def test_lite_review_context_includes_pr(self, initialized_state, capsys):
        state = load_state(initialized_state)
        state.epics["1"].lite_swarm.pr_number = 42
        state.epics["1"].lite_swarm.pr_url = "https://example/pr/42"
        save_state(state, initialized_state)

        cmd_get_context(_ns(
            state_file=str(initialized_state),
            target_command="lite_review",
            epic=1,
        ))
        ctx = json.loads(capsys.readouterr().out)
        assert ctx["pr_number"] == 42
        assert ctx["pr_url"] == "https://example/pr/42"

    def test_unknown_target_fails(self, initialized_state, capsys):
        exit_code = cmd_get_context(_ns(
            state_file=str(initialized_state),
            target_command="bogus",
            epic=None,
        ))
        assert exit_code == 1


# ---------------------------------------------------------------------------
# cmd_complete
# ---------------------------------------------------------------------------

class TestCmdComplete:
    def test_complete_lite_plan_appends_stage(self, initialized_state, capsys):
        # Reset state to pre-plan-convergence
        state = load_state(initialized_state)
        state.lite_plan.convergence = LiteConvergence(converged=False)
        state.lite_plan.stages_completed = ["A"]
        state.lite_plan.status = "in_progress"
        save_state(state, initialized_state)

        cmd_complete(_ns(
            state_file=str(initialized_state),
            target_command="lite_plan",
            epic=None,
            stage="B",
            output_paths=None,
            converged=False,
            decided_by=None,
            reason=None,
        ))
        reloaded = load_state(initialized_state)
        assert "B" in reloaded.lite_plan.stages_completed

    def test_complete_lite_plan_with_converged_sets_convergence(
        self, initialized_state, capsys,
    ):
        state = load_state(initialized_state)
        state.lite_plan.convergence = LiteConvergence(converged=False)
        save_state(state, initialized_state)

        cmd_complete(_ns(
            state_file=str(initialized_state),
            target_command="lite_plan",
            epic=None,
            stage=None,
            output_paths=None,
            converged=True,
            decided_by="test",
            reason="done",
        ))
        reloaded = load_state(initialized_state)
        assert reloaded.lite_plan.convergence.converged is True
        assert reloaded.lite_plan.convergence.reason == "done"

    def test_complete_lite_swarm_promotes_pr_created(self, initialized_state, capsys):
        cmd_complete(_ns(
            state_file=str(initialized_state),
            target_command="lite_swarm",
            epic=1,
            pr_url="https://example/pr/10",
            pr_number=10,
            integration_branch=None,
            stage=None,
            output_paths=None,
            converged=False,
            decided_by=None,
            reason=None,
        ))
        reloaded = load_state(initialized_state)
        assert reloaded.epics["1"].lite_swarm.pr_number == 10
        assert reloaded.epics["1"].lite_swarm.status == "pr_created"

    def test_complete_lite_review_increments_iteration(self, initialized_state):
        cmd_complete(_ns(
            state_file=str(initialized_state),
            target_command="lite_review",
            epic=1,
            report_path="review-1.md",
            findings_summary=json.dumps({"p1": 0, "p2": 2, "p3": 1}),
            stage=None,
            output_paths=None,
            converged=False,
            decided_by=None,
            reason=None,
        ))
        reloaded = load_state(initialized_state)
        review = reloaded.epics["1"].lite_review
        assert review.review_iteration == 1
        assert review.findings_summary == {"p1": 0, "p2": 2, "p3": 1}
        assert "review-1.md" in review.review_reports


# ---------------------------------------------------------------------------
# cmd_mark_converged
# ---------------------------------------------------------------------------

class TestCmdMarkConverged:
    def test_mark_lite_plan(self, initialized_state):
        state = load_state(initialized_state)
        state.lite_plan.convergence = LiteConvergence(converged=False)
        save_state(state, initialized_state)

        cmd_mark_converged(_ns(
            state_file=str(initialized_state),
            target_command="lite_plan",
            epic=None,
            reason="manual override",
        ))
        reloaded = load_state(initialized_state)
        assert reloaded.lite_plan.convergence.converged is True
        assert reloaded.lite_plan.convergence.reason == "manual override"

    def test_mark_lite_swarm_requires_epic(self, initialized_state, capsys):
        exit_code = cmd_mark_converged(_ns(
            state_file=str(initialized_state),
            target_command="lite_swarm",
            epic=None,
            reason="x",
        ))
        assert exit_code == 1

    def test_mark_lite_swarm_sets_status_and_convergence(self, initialized_state):
        cmd_mark_converged(_ns(
            state_file=str(initialized_state),
            target_command="lite_swarm",
            epic=1,
            reason="auto-merged",
        ))
        reloaded = load_state(initialized_state)
        swarm = reloaded.epics["1"].lite_swarm
        assert swarm.status == "converged"
        assert swarm.convergence.converged is True


# ---------------------------------------------------------------------------
# cmd_set_swarm_status
# ---------------------------------------------------------------------------

class TestCmdSetSwarmStatus:
    def test_invalid_status_rejected(self, initialized_state, capsys):
        exit_code = cmd_set_swarm_status(_ns(
            state_file=str(initialized_state),
            epic=1,
            status_value="bogus",
            pr_url=None, pr_number=None, integration_branch=None,
        ))
        assert exit_code == 1

    def test_updates_status_and_pr_metadata(self, initialized_state):
        cmd_set_swarm_status(_ns(
            state_file=str(initialized_state),
            epic=1,
            status_value="pr_created",
            pr_url="https://example/pr/5",
            pr_number=5,
            integration_branch=None,
        ))
        reloaded = load_state(initialized_state)
        swarm = reloaded.epics["1"].lite_swarm
        assert swarm.status == "pr_created"
        assert swarm.pr_number == 5

    def test_converged_status_sets_convergence(self, initialized_state):
        cmd_set_swarm_status(_ns(
            state_file=str(initialized_state),
            epic=1,
            status_value="converged",
            pr_url=None, pr_number=None, integration_branch=None,
        ))
        reloaded = load_state(initialized_state)
        assert reloaded.epics["1"].lite_swarm.convergence.converged is True


# ---------------------------------------------------------------------------
# cmd_add_review_report
# ---------------------------------------------------------------------------

class TestCmdAddReviewReport:
    def test_appends_report(self, initialized_state):
        cmd_add_review_report(_ns(
            state_file=str(initialized_state),
            epic=1,
            report_path="review-42.md",
        ))
        reloaded = load_state(initialized_state)
        assert "review-42.md" in reloaded.epics["1"].lite_review.review_reports
        assert reloaded.epics["1"].lite_review.status == "in_progress"

    def test_idempotent_on_duplicate_path(self, initialized_state):
        args = _ns(state_file=str(initialized_state), epic=1,
                   report_path="review-1.md")
        cmd_add_review_report(args)
        cmd_add_review_report(args)
        reloaded = load_state(initialized_state)
        assert reloaded.epics["1"].lite_review.review_reports.count("review-1.md") == 1


# ---------------------------------------------------------------------------
# cmd_init_epics
# ---------------------------------------------------------------------------

class TestCmdInitEpics:
    def test_populates_epics_dict(self, eigen_root):
        path = resolve_state_file(eigen_root)
        s = create_initial_state("x")
        s.lite_plan.convergence = LiteConvergence(converged=True)
        save_state(s, path)

        cmd_init_epics(_ns(
            state_file=str(path),
            epics_json=json.dumps([
                {"epic": 1, "is_e2e_epic": False},
                {"epic": 2, "is_e2e_epic": True},
            ]),
        ))
        reloaded = load_state(path)
        assert reloaded.epic_count == 2
        assert set(reloaded.epics.keys()) == {"1", "2"}
        assert reloaded.epics["1"].epic_path == "phases/phase_1/epic_1/"
        assert reloaded.epics["2"].is_e2e_epic is True
        assert reloaded.epics["1"].lite_swarm.integration_branch == "feat/P1.E1"

    def test_invalid_json_rejected(self, initialized_state):
        exit_code = cmd_init_epics(_ns(
            state_file=str(initialized_state),
            epics_json="not json",
        ))
        assert exit_code == 1

    def test_empty_list_rejected(self, initialized_state):
        exit_code = cmd_init_epics(_ns(
            state_file=str(initialized_state),
            epics_json="[]",
        ))
        assert exit_code == 1


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

class TestDispatch:
    def test_unknown_command_returns_error(self, capsys):
        exit_code = dispatch(_ns(command="bogus"))
        assert exit_code == 1
