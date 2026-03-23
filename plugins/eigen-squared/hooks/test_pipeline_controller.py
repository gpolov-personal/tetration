"""Tests for the eigen-squared pipeline controller hook.

Covers all state transitions, the 6 bugs found during design review,
branch resolution, and retry logic.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

# Import the module under test
# The hook is designed to be imported when EIGEN_ROOT may not exist,
# so we set env vars before import.
os.environ["EIGEN_ROOT"] = "/tmp/test_eigen"
os.environ["EIGEN_BRANCH"] = "main"
os.environ["CLAUDE_TASKS_API"] = "http://localhost:8332"

import pipeline_controller as pc


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────


def make_convergence_pair(
    main_status="not_started",
    main_fc=False,
    main_converged=False,
    deepen_status="not_started",
    deepen_fc=False,
):
    """Build a main/deepen state pair for testing."""
    main = {
        "status": main_status,
        "feedback_consumed": main_fc,
        "convergence": {"converged": main_converged},
        "iteration": 0,
    }
    deepen = {
        "status": deepen_status,
        "feedback_consumed": deepen_fc,
        "iteration": 0,
    }
    return main, deepen


def make_swarm_state(status="not_started", converged=False, review_iteration=0,
                     integration_branch=None, manifest_path=None):
    """Build a swarm_execution state for testing."""
    return {
        "status": status,
        "convergence": {"converged": converged},
        "review_iteration": review_iteration,
        "integration_branch": integration_branch,
        "manifest_path": manifest_path,
        "pr_url": None,
        "pr_number": None,
    }


def make_epic_plan(
    plan_status="not_started",
    plan_converged=False,
    plan_fc=False,
    deepen_status="not_started",
    deepen_fc=False,
    swarm_status="not_started",
    swarm_converged=False,
    swarm_review_iteration=0,
    integration_branch=None,
    manifest_path=None,
):
    """Build a complete epic plan entry."""
    return {
        "plan_phase_epic": {
            "status": plan_status,
            "feedback_consumed": plan_fc,
            "convergence": {"converged": plan_converged},
            "iteration": 0,
        },
        "deepen_plan_phase_epic": {
            "status": deepen_status,
            "feedback_consumed": deepen_fc,
            "iteration": 0,
        },
        "swarm_execution": make_swarm_state(
            status=swarm_status,
            converged=swarm_converged,
            review_iteration=swarm_review_iteration,
            integration_branch=integration_branch,
            manifest_path=manifest_path,
        ),
    }


def make_phase(
    bootstrap_converged=True,
    space_split_converged=True,
    phase_review_status="not_started",
    plans=None,
    include_bootstrap=True,
):
    """Build a phase state entry."""
    phase = {
        "space_split": {
            "status": "completed",
            "feedback_consumed": True,
            "convergence": {"converged": space_split_converged},
        },
        "deepen_space_split": {
            "status": "completed",
            "feedback_consumed": False,
        },
        "phase_review": {"status": phase_review_status},
        "plans": plans or {},
    }
    if include_bootstrap:
        phase["bootstrap"] = {
            "status": "completed",
            "feedback_consumed": True,
            "convergence": {"converged": bootstrap_converged},
        }
        phase["deepen_bootstrap"] = {
            "status": "completed",
            "feedback_consumed": False,
        }
    return phase


def make_pipeline_state(
    time_split_converged=True,
    phase_count=1,
    phases=None,
):
    """Build a complete pipeline_state.json structure."""
    return {
        "state": {
            "time_split": {
                "status": "completed",
                "feedback_consumed": True,
                "convergence": {"converged": time_split_converged},
                "phase_count": phase_count,
            },
            "deepen_time_split": {
                "status": "completed",
                "feedback_consumed": False,
            },
            "phases": phases or {},
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONVERGENCE PAIR TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestNextForConvergencePair:
    """Tests for the universal convergence pair logic."""

    def test_converged_returns_converged(self):
        main, deepen = make_convergence_pair(main_converged=True)
        assert pc.next_for_convergence_pair(main, deepen)[0] == "converged"

    def test_not_started_returns_run_main(self):
        main, deepen = make_convergence_pair(main_status="not_started")
        assert pc.next_for_convergence_pair(main, deepen)[0] == "run_main"

    def test_main_completed_deepen_not_started_returns_run_deepen(self):
        main, deepen = make_convergence_pair(
            main_status="completed", deepen_status="not_started"
        )
        assert pc.next_for_convergence_pair(main, deepen)[0] == "run_deepen"

    def test_fresh_feedback_returns_run_main(self):
        """After deepen runs, main_fc=False means fresh feedback available."""
        main, deepen = make_convergence_pair(
            main_status="completed",
            main_fc=False,
            deepen_status="completed",
        )
        assert pc.next_for_convergence_pair(main, deepen)[0] == "run_main"

    def test_feedback_consumed_returns_run_deepen(self):
        """After main consumes feedback (main_fc=True), deepen re-analyzes."""
        main, deepen = make_convergence_pair(
            main_status="completed",
            main_fc=True,
            deepen_status="completed",
        )
        assert pc.next_for_convergence_pair(main, deepen)[0] == "run_deepen"

    # ── BUG #1 regression: MFC=True, DFC=False should NOT return None ──

    def test_bug1_completed_completed_mfc_true_dfc_false(self):
        """Regression: this state used to return None (dead end)."""
        main, deepen = make_convergence_pair(
            main_status="completed",
            main_fc=True,
            deepen_status="completed",
            deepen_fc=False,
        )
        result = pc.next_for_convergence_pair(main, deepen)
        assert result is not None
        assert result[0] == "run_deepen"

    def test_bug1_iterating_not_started_mfc_true_dfc_false(self):
        """Regression: this state used to return None (dead end)."""
        main, deepen = make_convergence_pair(
            main_status="iterating",
            main_fc=True,
            deepen_status="not_started",
            deepen_fc=False,
        )
        result = pc.next_for_convergence_pair(main, deepen)
        assert result is not None
        assert result[0] == "run_deepen"

    def test_bug1_iterating_completed_mfc_true_dfc_false(self):
        """Regression: this state used to return None (dead end)."""
        main, deepen = make_convergence_pair(
            main_status="iterating",
            main_fc=True,
            deepen_status="completed",
            deepen_fc=False,
        )
        result = pc.next_for_convergence_pair(main, deepen)
        assert result is not None
        assert result[0] == "run_deepen"

    def test_never_returns_none(self):
        """Exhaustive: no combination of inputs returns None."""
        for main_status in ("not_started", "completed", "iterating"):
            for main_fc in (True, False):
                for main_conv in (True, False):
                    for deepen_status in ("not_started", "completed"):
                        for deepen_fc in (True, False):
                            main, deepen = make_convergence_pair(
                                main_status=main_status,
                                main_fc=main_fc,
                                main_converged=main_conv,
                                deepen_status=deepen_status,
                                deepen_fc=deepen_fc,
                            )
                            result = pc.next_for_convergence_pair(main, deepen)
                            assert result is not None, (
                                f"None for main_status={main_status}, "
                                f"main_fc={main_fc}, main_conv={main_conv}, "
                                f"deepen_status={deepen_status}, deepen_fc={deepen_fc}"
                            )


# ─────────────────────────────────────────────────────────────────────────────
# SWARM PAIR TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestNextForSwarmPair:
    """Tests for orchestrate_swarm / review_swarm_pr logic."""

    def test_not_started_returns_orchestrate(self):
        swarm = make_swarm_state(status="not_started")
        assert pc.next_for_swarm_pair(swarm)[0] == "run_orchestrate"

    def test_pr_created_first_time_returns_review(self):
        swarm = make_swarm_state(status="pr_created", review_iteration=0)
        assert pc.next_for_swarm_pair(swarm)[0] == "run_review"

    def test_iterating_returns_orchestrate(self):
        swarm = make_swarm_state(status="iterating", review_iteration=1)
        assert pc.next_for_swarm_pair(swarm)[0] == "run_orchestrate"

    def test_converged_returns_converged(self):
        swarm = make_swarm_state(status="converged", converged=True)
        assert pc.next_for_swarm_pair(swarm)[0] == "converged"

    # ── BUG #2 regression: pr_created + review_iteration > 0 must be review ──

    def test_bug2_pr_created_after_fixups_returns_review(self):
        """Regression: pr_created with review_iteration>0 used to return run_orchestrate."""
        swarm = make_swarm_state(status="pr_created", review_iteration=1)
        result = pc.next_for_swarm_pair(swarm)
        assert result[0] == "run_review", (
            "pr_created ALWAYS means review, even after fixups"
        )

    def test_bug2_pr_created_after_many_fixups_returns_review(self):
        swarm = make_swarm_state(status="pr_created", review_iteration=5)
        assert pc.next_for_swarm_pair(swarm)[0] == "run_review"

    def test_inconsistent_status_converged_but_flag_false(self):
        """status=converged but convergence.converged=false — trust status."""
        swarm = make_swarm_state(status="converged", converged=False)
        assert pc.next_for_swarm_pair(swarm)[0] == "converged"


# ─────────────────────────────────────────────────────────────────────────────
# DETERMINE_NEXT TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestDetermineNext:
    """Tests for the full pipeline walk."""

    def test_fresh_pipeline_schedules_time_split(self):
        state = make_pipeline_state(time_split_converged=False)
        state["state"]["time_split"]["status"] = "not_started"
        result = pc.determine_next(state)
        assert result is not None
        assert result[0] == "time_split"

    def test_time_split_completed_schedules_deepen(self):
        """After time_split completes for the first time, deepen should run.

        make_pipeline_state defaults deepen to "completed", so we must
        explicitly set it to "not_started" to simulate first run.
        """
        state = make_pipeline_state(time_split_converged=False)
        state["state"]["time_split"]["status"] = "completed"
        state["state"]["time_split"]["feedback_consumed"] = True
        state["state"]["deepen_time_split"]["status"] = "not_started"
        result = pc.determine_next(state)
        assert result[0] == "deepen_time_split"

    def test_time_split_converged_goes_to_bootstrap(self):
        phase = make_phase(bootstrap_converged=False)
        phase["bootstrap"]["status"] = "not_started"
        state = make_pipeline_state(phases={"1": phase})
        result = pc.determine_next(state)
        assert result[0] == "bootstrap"
        assert result[1]["phase"] == 1

    def test_phase_approved_skips_to_next(self):
        """Phase 1 approved → walk continues to phase 2."""
        phase1 = make_phase(phase_review_status="approved")
        phase2 = make_phase(bootstrap_converged=False)
        phase2["bootstrap"]["status"] = "not_started"
        state = make_pipeline_state(phase_count=2, phases={"1": phase1, "2": phase2})
        result = pc.determine_next(state)
        assert result[0] == "bootstrap"
        assert result[1]["phase"] == 2

    # ── BUG #3 regression: "testing" must STOP, not fall through ──

    def test_bug3_testing_phase_review_stops(self):
        """Regression: testing status used to fall through to next phase."""
        epic = make_epic_plan(swarm_status="converged", swarm_converged=True,
                              plan_status="completed", plan_converged=True)
        phase = make_phase(phase_review_status="testing", plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        # Mock epic_order to return [1]
        with patch.object(pc, "load_epic_order", return_value=[1]):
            result = pc.determine_next(state)
        assert result is None, "testing phase_review should stop (human checkpoint)"

    # ── BUG #4 regression: missing bootstrap keys don't crash ──

    def test_bug4_phase_without_bootstrap_keys(self):
        """Regression: phases without bootstrap keys used to KeyError."""
        phase = make_phase(include_bootstrap=False, space_split_converged=False)
        phase["space_split"]["status"] = "not_started"
        state = make_pipeline_state(phases={"1": phase})
        result = pc.determine_next(state)
        # Should skip bootstrap (not present) and go to space_split
        assert result[0] == "space_split"

    # ── BUG #5 regression: missing plan entry schedules plan, not skip ──

    def test_bug5_missing_plan_schedules_plan(self):
        """Regression: plan is None used to skip epic (continue), falsely completing phase."""
        phase = make_phase(plans={})  # No plans at all
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1]):
            with patch.object(pc, "epic_dependencies_met", return_value=True):
                result = pc.determine_next(state)
        assert result is not None
        assert result[0] == "plan_phase_epic"
        assert result[1]["epic"] == 1

    def test_missing_plan_with_unmet_deps_waits(self):
        """If epic dependencies aren't met, can't plan it yet."""
        phase = make_phase(plans={})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1, 2]):
            with patch.object(pc, "epic_dependencies_met", return_value=False):
                result = pc.determine_next(state)
        # All epics have unmet deps → phase not complete → stop
        assert result is None

    # ── BUG #6: create_issues inferred from swarm state ──

    def test_bug6_create_issues_inferred(self):
        """create_issues detected when plan converged but swarm not started."""
        epic = make_epic_plan(
            plan_status="completed", plan_converged=True,
            swarm_status="not_started", manifest_path=None,
        )
        phase = make_phase(plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1]):
            result = pc.determine_next(state)
        assert result[0] == "create_issues_from_plan_swarm"

    def test_all_phases_approved_returns_none(self):
        phase = make_phase(phase_review_status="approved")
        state = make_pipeline_state(phases={"1": phase})
        result = pc.determine_next(state)
        assert result is None

    def test_phase_count_zero_returns_none(self):
        state = make_pipeline_state(phase_count=0)
        result = pc.determine_next(state)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# BRANCH RESOLUTION TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveBranch:
    """Tests for branch resolution logic."""

    def test_time_split_resolves_to_eigen_branch(self):
        state = make_pipeline_state(time_split_converged=False)
        state["state"]["time_split"]["status"] = "not_started"
        branch = pc.resolve_branch(state)
        assert branch == "main"

    def test_orchestrate_resolves_to_integration_branch(self):
        epic = make_epic_plan(
            plan_status="completed", plan_converged=True,
            swarm_status="not_started",
            manifest_path="some/path",
            integration_branch="feat/P1.E1",
        )
        # Set swarm to a state where orchestrate is next
        # manifest_path is set but status is not_started → orchestrate
        # Actually, if manifest_path is set, the create_issues check passes
        # and we go to next_for_swarm_pair which returns run_orchestrate
        phase = make_phase(plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1]):
            branch = pc.resolve_branch(state)
        assert branch == "feat/P1.E1"

    def test_review_resolves_to_integration_branch(self):
        epic = make_epic_plan(
            plan_status="completed", plan_converged=True,
            swarm_status="pr_created",
            integration_branch="feat/P1.E2",
            manifest_path="some/path",
        )
        phase = make_phase(plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1]):
            branch = pc.resolve_branch(state)
        assert branch == "feat/P1.E2"

    def test_plan_phase_epic_resolves_to_eigen_branch(self):
        phase = make_phase(plans={})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1]):
            with patch.object(pc, "epic_dependencies_met", return_value=True):
                branch = pc.resolve_branch(state)
        assert branch == "main"

    def test_complete_pipeline_returns_empty(self):
        phase = make_phase(phase_review_status="approved")
        state = make_pipeline_state(phases={"1": phase})
        branch = pc.resolve_branch(state)
        assert branch == ""


# ─────────────────────────────────────────────────────────────────────────────
# RETRY LOGIC TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestRetryLogic:

    def test_first_run_returns_attempt_1(self, tmp_path):
        """No log file → attempt 1, proceed."""
        with patch.object(pc, "HOOK_LOG", tmp_path / "hook_log.jsonl"):
            proceed, attempt = pc.check_retry("time_split", "initiative")
        assert proceed is True
        assert attempt == 1

    def test_different_command_resets(self, tmp_path):
        """Different command from last confirmed → attempt 1."""
        log_file = tmp_path / "hook_log.jsonl"
        log_file.write_text(json.dumps({
            "command": "time_split",
            "context_key": "initiative",
            "status": "confirmed",
            "attempt": 1,
            "timestamp": "2026-01-01T00:00:00Z",
        }) + "\n")
        with patch.object(pc, "HOOK_LOG", log_file):
            proceed, attempt = pc.check_retry("deepen_time_split", "initiative")
        assert proceed is True
        assert attempt == 1

    def test_same_command_increments_attempt(self, tmp_path):
        """Same command + context → attempt incremented."""
        log_file = tmp_path / "hook_log.jsonl"
        log_file.write_text(json.dumps({
            "command": "time_split",
            "context_key": "initiative",
            "status": "confirmed",
            "attempt": 1,
            "timestamp": "2026-01-01T00:00:00Z",
        }) + "\n")
        with patch.object(pc, "HOOK_LOG", log_file):
            proceed, attempt = pc.check_retry("time_split", "initiative")
        assert proceed is True
        assert attempt == 2

    def test_max_retries_stops(self, tmp_path):
        """After MAX_COMMAND_RETRIES, should_proceed is False."""
        log_file = tmp_path / "hook_log.jsonl"
        log_file.write_text(json.dumps({
            "command": "bootstrap",
            "context_key": "phase:P1",
            "status": "confirmed",
            "attempt": pc.MAX_COMMAND_RETRIES,
            "timestamp": "2026-01-01T00:00:00Z",
        }) + "\n")
        with patch.object(pc, "HOOK_LOG", log_file):
            with patch.object(pc, "alert"):
                with patch.object(pc, "log_entry"):
                    proceed, attempt = pc.check_retry("bootstrap", "phase:P1")
        assert proceed is False


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT KEY TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestMakeContextKey:

    def test_initiative_scope(self):
        assert pc.make_context_key({"scope": "initiative"}) == "initiative"

    def test_phase_scope(self):
        assert pc.make_context_key({"scope": "phase", "phase": 1}) == "phase:P1"

    def test_epic_scope(self):
        key = pc.make_context_key({"scope": "epic", "phase": 2, "epic": 3})
        assert key == "epic:P2:E3"


# ─────────────────────────────────────────────────────────────────────────────
# v1.3.1 BUG FIX REGRESSION TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestV131Fixes:
    """Regression tests for bugs found in v1.3.0 audit."""

    def test_missing_state_key_returns_none(self):
        """#1: Missing state.time_split shouldn't crash."""
        state = {"state": {}}
        result = pc.determine_next(state)
        assert result is None

    def test_missing_deepen_space_split_no_crash(self):
        """#4: Phase with space_split but no deepen_space_split."""
        phase = make_phase()
        del phase["deepen_space_split"]
        phase["space_split"]["status"] = "not_started"
        phase["space_split"]["convergence"]["converged"] = False
        state = make_pipeline_state(phases={"1": phase})
        result = pc.determine_next(state)
        assert result is not None
        assert result[0] == "space_split"

    def test_missing_plan_sub_keys_no_crash(self):
        """#5: Plan entry exists but missing plan_phase_epic sub-key."""
        phase = make_phase(plans={"1": {"swarm_execution": make_swarm_state()}})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1]):
            with patch.object(pc, "epic_dependencies_met", return_value=True):
                result = pc.determine_next(state)
        assert result is not None
        assert result[0] == "plan_phase_epic"

    def test_phase_count_as_string(self):
        """#6: phase_count stored as string '3' not int 3."""
        state = make_pipeline_state(time_split_converged=True, phase_count=1)
        state["state"]["time_split"]["phase_count"] = "1"
        phase = make_phase(bootstrap_converged=False)
        phase["bootstrap"]["status"] = "not_started"
        state["state"]["phases"] = {"1": phase}
        result = pc.determine_next(state)
        assert result is not None
        assert result[0] == "bootstrap"

    def test_noop_log_not_matched_by_retry(self, tmp_path):
        """#7: Noop log entries should not be matched by check_retry."""
        log_file = tmp_path / "hook_log.jsonl"
        # Write a noop entry (status="noop", no command)
        log_file.write_text(json.dumps({
            "action": "noop",
            "command": None,
            "context_key": None,
            "status": "noop",
            "reason": "human checkpoint",
            "timestamp": "2026-01-01T00:00:00Z",
        }) + "\n")
        with patch.object(pc, "HOOK_LOG", log_file):
            proceed, attempt = pc.check_retry("time_split", "initiative")
        # Should not match noop → attempt 1, proceed
        assert proceed is True
        assert attempt == 1

    def test_deadlock_detected_not_silent(self):
        """#10: All epics blocked on deps should alert, not silently return None."""
        phase = make_phase(plans={})
        state = make_pipeline_state(phases={"1": phase})
        with patch.object(pc, "load_epic_order", return_value=[1, 2]):
            with patch.object(pc, "epic_dependencies_met", return_value=False):
                with patch.object(pc, "alert") as mock_alert:
                    result = pc.determine_next(state)
        assert result is None
        # Should have called alert with warning about unmet deps
        mock_alert.assert_called()
        assert "unmet dependencies" in mock_alert.call_args[0][1]

    def test_last_confirmed_ignores_noop(self, tmp_path):
        """last_confirmed_entry skips noop entries (status != 'confirmed')."""
        log_file = tmp_path / "hook_log.jsonl"
        lines = [
            json.dumps({"command": "time_split", "context_key": "initiative",
                        "status": "confirmed", "attempt": 1, "timestamp": "t1"}),
            json.dumps({"action": "noop", "command": None, "status": "noop",
                        "timestamp": "t2"}),
        ]
        log_file.write_text("\n".join(lines) + "\n")
        with patch.object(pc, "HOOK_LOG", log_file):
            entry = pc.last_confirmed_entry()
        assert entry is not None
        assert entry["command"] == "time_split"

    def test_last_confirmed_requires_command_field(self, tmp_path):
        """last_confirmed_entry requires a non-null command field."""
        log_file = tmp_path / "hook_log.jsonl"
        # Entry with confirmed status but no command — should be skipped
        log_file.write_text(json.dumps({
            "status": "confirmed",
            "timestamp": "t1",
        }) + "\n")
        with patch.object(pc, "HOOK_LOG", log_file):
            entry = pc.last_confirmed_entry()
        assert entry is None
