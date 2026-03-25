"""Tests for pipeline state transitions.

Ported from hooks/test_pipeline_controller.py — covers all state transitions,
the 6 bugs found during design review, branch resolution, and context keys.
"""

import json
import pytest
from unittest.mock import patch

from cli.transitions import (
    next_for_convergence_pair,
    next_for_swarm_pair,
    determine_next,
    resolve_branch,
    make_context_key,
)


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


def make_swarm_state(
    status="not_started",
    converged=False,
    review_iteration=0,
    integration_branch=None,
    manifest_path=None,
):
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

    def test_converged_returns_converged(self):
        main, deepen = make_convergence_pair(main_converged=True)
        assert next_for_convergence_pair(main, deepen)[0] == "converged"

    def test_not_started_returns_run_main(self):
        main, deepen = make_convergence_pair(main_status="not_started")
        assert next_for_convergence_pair(main, deepen)[0] == "run_main"

    def test_main_completed_deepen_not_started_returns_run_deepen(self):
        main, deepen = make_convergence_pair(
            main_status="completed", deepen_status="not_started"
        )
        assert next_for_convergence_pair(main, deepen)[0] == "run_deepen"

    def test_fresh_feedback_returns_run_main(self):
        main, deepen = make_convergence_pair(
            main_status="completed", main_fc=False, deepen_status="completed",
        )
        assert next_for_convergence_pair(main, deepen)[0] == "run_main"

    def test_feedback_consumed_returns_run_deepen(self):
        main, deepen = make_convergence_pair(
            main_status="completed", main_fc=True, deepen_status="completed",
        )
        assert next_for_convergence_pair(main, deepen)[0] == "run_deepen"

    def test_bug1_completed_completed_mfc_true_dfc_false(self):
        main, deepen = make_convergence_pair(
            main_status="completed", main_fc=True,
            deepen_status="completed", deepen_fc=False,
        )
        result = next_for_convergence_pair(main, deepen)
        assert result is not None
        assert result[0] == "run_deepen"

    def test_bug1_iterating_not_started_mfc_true_dfc_false(self):
        main, deepen = make_convergence_pair(
            main_status="iterating", main_fc=True,
            deepen_status="not_started", deepen_fc=False,
        )
        result = next_for_convergence_pair(main, deepen)
        assert result is not None
        assert result[0] == "run_deepen"

    def test_bug1_iterating_completed_mfc_true_dfc_false(self):
        main, deepen = make_convergence_pair(
            main_status="iterating", main_fc=True,
            deepen_status="completed", deepen_fc=False,
        )
        result = next_for_convergence_pair(main, deepen)
        assert result is not None
        assert result[0] == "run_deepen"

    def test_never_returns_none(self):
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
                            result = next_for_convergence_pair(main, deepen)
                            assert result is not None, (
                                f"None for {main_status=}, {main_fc=}, "
                                f"{main_conv=}, {deepen_status=}, {deepen_fc=}"
                            )


# ─────────────────────────────────────────────────────────────────────────────
# SWARM PAIR TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestNextForSwarmPair:

    def test_not_started_returns_orchestrate(self):
        assert next_for_swarm_pair(make_swarm_state())[0] == "run_orchestrate"

    def test_pr_created_first_time_returns_review(self):
        swarm = make_swarm_state(status="pr_created", review_iteration=0)
        assert next_for_swarm_pair(swarm)[0] == "run_review"

    def test_iterating_returns_orchestrate(self):
        swarm = make_swarm_state(status="iterating", review_iteration=1)
        assert next_for_swarm_pair(swarm)[0] == "run_orchestrate"

    def test_converged_returns_converged(self):
        swarm = make_swarm_state(status="converged", converged=True)
        assert next_for_swarm_pair(swarm)[0] == "converged"

    def test_bug2_pr_created_after_fixups_returns_review(self):
        swarm = make_swarm_state(status="pr_created", review_iteration=1)
        assert next_for_swarm_pair(swarm)[0] == "run_review"

    def test_bug2_pr_created_after_many_fixups_returns_review(self):
        swarm = make_swarm_state(status="pr_created", review_iteration=5)
        assert next_for_swarm_pair(swarm)[0] == "run_review"

    def test_inconsistent_status_converged_but_flag_false(self):
        swarm = make_swarm_state(status="converged", converged=False)
        assert next_for_swarm_pair(swarm)[0] == "converged"


# ─────────────────────────────────────────────────────────────────────────────
# DETERMINE_NEXT TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestDetermineNext:

    def test_fresh_pipeline_schedules_time_split(self):
        state = make_pipeline_state(time_split_converged=False)
        state["state"]["time_split"]["status"] = "not_started"
        result = determine_next(state)
        assert result is not None
        assert result[0] == "time_split"

    def test_time_split_completed_schedules_deepen(self):
        state = make_pipeline_state(time_split_converged=False)
        state["state"]["time_split"]["status"] = "completed"
        state["state"]["time_split"]["feedback_consumed"] = True
        state["state"]["deepen_time_split"]["status"] = "not_started"
        result = determine_next(state)
        assert result[0] == "deepen_time_split"

    def test_time_split_converged_goes_to_bootstrap(self):
        phase = make_phase(bootstrap_converged=False)
        phase["bootstrap"]["status"] = "not_started"
        state = make_pipeline_state(phases={"1": phase})
        result = determine_next(state)
        assert result[0] == "bootstrap"
        assert result[1]["phase"] == 1

    def test_phase_approved_skips_to_next(self):
        phase1 = make_phase(phase_review_status="approved")
        phase2 = make_phase(bootstrap_converged=False)
        phase2["bootstrap"]["status"] = "not_started"
        state = make_pipeline_state(phase_count=2, phases={"1": phase1, "2": phase2})
        result = determine_next(state)
        assert result[0] == "bootstrap"
        assert result[1]["phase"] == 2

    def test_bug3_testing_phase_review_stops(self):
        epic = make_epic_plan(
            swarm_status="converged", swarm_converged=True,
            plan_status="completed", plan_converged=True,
        )
        phase = make_phase(phase_review_status="testing", plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            result = determine_next(state)
        assert result is None

    def test_bug4_phase_without_bootstrap_keys(self):
        phase = make_phase(include_bootstrap=False, space_split_converged=False)
        phase["space_split"]["status"] = "not_started"
        state = make_pipeline_state(phases={"1": phase})
        result = determine_next(state)
        assert result[0] == "space_split"

    def test_bug5_missing_plan_schedules_plan(self):
        phase = make_phase(plans={})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            with patch("cli.transitions.epic_dependencies_met", return_value=True):
                result = determine_next(state)
        assert result is not None
        assert result[0] == "plan_phase_epic"
        assert result[1]["epic"] == 1

    def test_missing_plan_with_unmet_deps_waits(self):
        phase = make_phase(plans={})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1, 2]):
            with patch("cli.transitions.epic_dependencies_met", return_value=False):
                result = determine_next(state)
        assert result is None

    def test_bug6_create_issues_inferred(self):
        epic = make_epic_plan(
            plan_status="completed", plan_converged=True,
            swarm_status="not_started", manifest_path=None,
        )
        phase = make_phase(plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            result = determine_next(state)
        assert result[0] == "create_issues_from_plan_swarm"

    def test_all_phases_approved_returns_none(self):
        phase = make_phase(phase_review_status="approved")
        state = make_pipeline_state(phases={"1": phase})
        result = determine_next(state)
        assert result is None

    def test_phase_count_zero_returns_none(self):
        state = make_pipeline_state(phase_count=0)
        result = determine_next(state)
        assert result is None

    def test_missing_state_key_returns_none(self):
        result = determine_next({"state": {}})
        assert result is None

    def test_missing_deepen_space_split_no_crash(self):
        phase = make_phase()
        del phase["deepen_space_split"]
        phase["space_split"]["status"] = "not_started"
        phase["space_split"]["convergence"]["converged"] = False
        state = make_pipeline_state(phases={"1": phase})
        result = determine_next(state)
        assert result is not None
        assert result[0] == "space_split"

    def test_missing_plan_sub_keys_no_crash(self):
        phase = make_phase(plans={"1": {"swarm_execution": make_swarm_state()}})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            with patch("cli.transitions.epic_dependencies_met", return_value=True):
                result = determine_next(state)
        assert result is not None
        assert result[0] == "plan_phase_epic"

    def test_phase_count_as_string(self):
        state = make_pipeline_state(time_split_converged=True, phase_count=1)
        state["state"]["time_split"]["phase_count"] = "1"
        phase = make_phase(bootstrap_converged=False)
        phase["bootstrap"]["status"] = "not_started"
        state["state"]["phases"] = {"1": phase}
        result = determine_next(state)
        assert result is not None
        assert result[0] == "bootstrap"


# ─────────────────────────────────────────────────────────────────────────────
# BRANCH RESOLUTION TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveBranch:

    def test_time_split_resolves_to_eigen_branch(self):
        state = make_pipeline_state(time_split_converged=False)
        state["state"]["time_split"]["status"] = "not_started"
        assert resolve_branch(state) == "main"

    def test_orchestrate_resolves_to_integration_branch(self):
        epic = make_epic_plan(
            plan_status="completed", plan_converged=True,
            swarm_status="not_started",
            manifest_path="some/path",
            integration_branch="feat/P1.E1",
        )
        phase = make_phase(plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            assert resolve_branch(state) == "feat/P1.E1"

    def test_review_resolves_to_integration_branch(self):
        epic = make_epic_plan(
            plan_status="completed", plan_converged=True,
            swarm_status="pr_created",
            integration_branch="feat/P1.E2",
            manifest_path="some/path",
        )
        phase = make_phase(plans={"1": epic})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            assert resolve_branch(state) == "feat/P1.E2"

    def test_plan_phase_epic_resolves_to_eigen_branch(self):
        phase = make_phase(plans={})
        state = make_pipeline_state(phases={"1": phase})
        with patch("cli.transitions.load_epic_order", return_value=[1]):
            with patch("cli.transitions.epic_dependencies_met", return_value=True):
                assert resolve_branch(state) == "main"

    def test_complete_pipeline_returns_empty(self):
        phase = make_phase(phase_review_status="approved")
        state = make_pipeline_state(phases={"1": phase})
        assert resolve_branch(state) == ""


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT KEY TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestMakeContextKey:

    def test_initiative_scope(self):
        assert make_context_key({"scope": "initiative"}) == "initiative"

    def test_phase_scope(self):
        assert make_context_key({"scope": "phase", "phase": 1}) == "phase:P1"

    def test_epic_scope(self):
        assert make_context_key({"scope": "epic", "phase": 2, "epic": 3}) == "epic:P2:E3"
