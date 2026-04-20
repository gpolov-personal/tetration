"""TDD tests for the lite pipeline state machine."""

from cli.transitions_lite import (
    determine_next_lite,
    make_context_key_lite,
    resolve_branch_lite,
    INTEGRATION_BRANCH_COMMANDS_LITE,
)


# ---------------------------------------------------------------------------
# Fixtures — dict-shaped pipeline state (what from_dict round-trips produce).
# determine_next_lite operates on raw dicts, mirroring squared's contract.
# ---------------------------------------------------------------------------

def _plan(converged: bool = False, status: str = "not_started") -> dict:
    return {
        "status": status,
        "iteration": 0,
        "stages_completed": [],
        "output_paths": {},
        "findings_summary": {"high": 0, "medium": 0, "low": 0},
        "convergence": {"converged": converged},
    }


def _swarm(
    status: str = "not_started",
    pr_number: int | None = None,
    integration_branch: str | None = None,
    converged: bool = False,
) -> dict:
    return {
        "status": status,
        "pr_url": None,
        "pr_number": pr_number,
        "integration_branch": integration_branch,
        "convergence": {"converged": converged},
    }


def _review(converged: bool = False, iteration: int = 0) -> dict:
    return {
        "status": "not_started" if iteration == 0 else "in_progress",
        "review_iteration": iteration,
        "findings_summary": {"p1": 0, "p2": 0, "p3": 0},
        "convergence": {"converged": converged},
        "review_reports": [],
    }


def _epic(
    epic_num: int,
    swarm: dict | None = None,
    review: dict | None = None,
    is_e2e: bool = False,
) -> dict:
    return {
        "epic_path": f"phases/phase_1/epic_{epic_num}/",
        "epic_file": f"phases/phase_1/epic_{epic_num}/epic.md",
        "plan_file": f"phases/phase_1/epic_{epic_num}/plan.md",
        "swarm_manifest": f"phases/phase_1/epic_{epic_num}/swarm-manifest.json",
        "is_e2e_epic": is_e2e,
        "lite_swarm": swarm or _swarm(integration_branch=f"feat/P1.E{epic_num}"),
        "lite_review": review or _review(),
    }


def _pipeline(
    feature_set: str = "my-initiative",
    lite_plan: dict | None = None,
    epics: dict | None = None,
    epic_count: int = 0,
) -> dict:
    return {
        "schema_version": "1.0.0",
        "feature_set": feature_set,
        "phase": 1,
        "epic_count": epic_count,
        "state": {
            "lite_plan": lite_plan or _plan(),
            "epics": epics or {},
        },
        "recommendations": [],
    }


# ---------------------------------------------------------------------------
# make_context_key_lite
# ---------------------------------------------------------------------------

class TestMakeContextKeyLite:
    def test_initiative_scope(self):
        assert make_context_key_lite({"scope": "initiative"}) == "initiative"

    def test_epic_scope(self):
        assert make_context_key_lite({"scope": "epic", "epic": 2}) == "epic:E2"

    def test_missing_scope_defaults_to_unknown(self):
        assert make_context_key_lite({"epic": 1}) == "unknown:E1"

    def test_large_epic_number(self):
        assert make_context_key_lite({"scope": "epic", "epic": 42}) == "epic:E42"

    def test_initiative_ignores_epic_field(self):
        """Scope wins: 'initiative' never carries an epic suffix."""
        assert make_context_key_lite({"scope": "initiative", "epic": 5}) == "initiative"


# ---------------------------------------------------------------------------
# determine_next_lite — stage 1: lite_plan must converge first
# ---------------------------------------------------------------------------

class TestDetermineNextLitePlanStage:
    def test_fresh_state_runs_lite_plan(self):
        state = _pipeline()
        result = determine_next_lite(state)
        assert result is not None
        cmd, ctx = result
        assert cmd == "lite_plan"
        assert ctx["scope"] == "initiative"
        assert ctx["feature_set"] == "my-initiative"

    def test_in_progress_lite_plan_reruns(self):
        state = _pipeline(lite_plan=_plan(status="in_progress"))
        cmd, _ = determine_next_lite(state)
        assert cmd == "lite_plan"

    def test_converged_plan_with_no_epics_returns_none(self):
        """Plan converged but epics dict empty — nothing to do."""
        state = _pipeline(lite_plan=_plan(converged=True))
        assert determine_next_lite(state) is None

    def test_missing_state_key_returns_none(self):
        """Data integrity: no state key → nothing to advance."""
        assert determine_next_lite({}) is None

    def test_missing_lite_plan_treated_as_not_started(self):
        state = {"state": {"epics": {}}}
        cmd, _ = determine_next_lite(state)
        assert cmd == "lite_plan"


# ---------------------------------------------------------------------------
# determine_next_lite — stage 2: walk epics sequentially
# ---------------------------------------------------------------------------

class TestDetermineNextLiteEpicStage:
    def test_first_epic_swarm_not_started_runs_swarm(self):
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={"1": _epic(1)},
            epic_count=1,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_swarm"
        assert ctx == {
            "scope": "epic",
            "epic": 1,
            "branch": "feat/P1.E1",
            "manifest_path": "phases/phase_1/epic_1/swarm-manifest.json",
        }

    def test_swarm_pr_created_triggers_review(self):
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="pr_created", pr_number=42,
                    integration_branch="feat/P1.E1",
                )),
            },
            epic_count=1,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_review"
        assert ctx["epic"] == 1
        assert ctx["pr_number"] == 42
        assert ctx["branch"] == "feat/P1.E1"

    def test_swarm_iterating_triggers_swarm_for_fixups(self):
        """When swarm is iterating (review just added fixup tasks to the
        manifest), the next action is lite_swarm to execute those fixups —
        matching squared's orchestrate_swarm/review_swarm_pr loop semantics.
        """
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="iterating", pr_number=42,
                    integration_branch="feat/P1.E1",
                )),
            },
            epic_count=1,
        )
        cmd, _ = determine_next_lite(state)
        assert cmd == "lite_swarm"

    def test_review_converged_but_swarm_not_yet_marked_continues_to_next_epic(self):
        """Review says 'converged' — caller will mark swarm converged on auto-merge.
        determine_next should skip this epic and move on.
        """
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="iterating", pr_number=42,
                    integration_branch="feat/P1.E1",
                ), review=_review(converged=True, iteration=2)),
                "2": _epic(2),
            },
            epic_count=2,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_swarm"
        assert ctx["epic"] == 2

    def test_swarm_converged_moves_to_next_epic(self):
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="converged", pr_number=10,
                    integration_branch="feat/P1.E1",
                    converged=True,
                ), review=_review(converged=True, iteration=1)),
                "2": _epic(2),
            },
            epic_count=2,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_swarm"
        assert ctx["epic"] == 2

    def test_all_epics_converged_returns_none(self):
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="converged", converged=True,
                    integration_branch="feat/P1.E1",
                ), review=_review(converged=True, iteration=1)),
                "2": _epic(2, swarm=_swarm(
                    status="converged", converged=True,
                    integration_branch="feat/P1.E2",
                ), review=_review(converged=True, iteration=1), is_e2e=True),
            },
            epic_count=2,
        )
        assert determine_next_lite(state) is None

    def test_epics_walked_in_numeric_order_not_string_order(self):
        """'10' comes after '2' numerically, not alphabetically."""
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "10": _epic(10),
                "2": _epic(2, swarm=_swarm(
                    status="converged", converged=True,
                    integration_branch="feat/P1.E2",
                ), review=_review(converged=True, iteration=1)),
            },
            epic_count=2,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_swarm"
        assert ctx["epic"] == 10

    def test_e2e_epic_treated_like_any_other_epic_in_ordering(self):
        """is_e2e_epic flag doesn't change transition logic — it's metadata."""
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="converged", converged=True,
                    integration_branch="feat/P1.E1",
                ), review=_review(converged=True, iteration=1)),
                "2": _epic(2, is_e2e=True),  # E2E epic, not started
            },
            epic_count=2,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_swarm"
        assert ctx["epic"] == 2

    def test_missing_swarm_manifest_still_returns_swarm_command(self):
        """Workers construct manifest path from epic_id; the state mirror
        may be None before first run. Don't crash on that.
        """
        epic_data = _epic(1)
        epic_data["swarm_manifest"] = None
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={"1": epic_data},
            epic_count=1,
        )
        cmd, ctx = determine_next_lite(state)
        assert cmd == "lite_swarm"
        assert ctx["epic"] == 1

    def test_iterating_with_prior_review_still_runs_swarm_for_fixups(self):
        """Even after a prior non-converged review, iterating swarm status
        means the swarm has fixup work queued — run lite_swarm, not
        lite_review (lite_review will fire again after the swarm completes).
        """
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1,
                    swarm=_swarm(status="iterating", pr_number=1,
                                 integration_branch="feat/P1.E1"),
                    review=_review(iteration=2, converged=False)),
            },
            epic_count=1,
        )
        cmd, _ = determine_next_lite(state)
        assert cmd == "lite_swarm"


# ---------------------------------------------------------------------------
# resolve_branch_lite
# ---------------------------------------------------------------------------

class TestResolveBranchLite:
    def test_lite_plan_uses_base_branch(self):
        state = _pipeline()
        assert resolve_branch_lite(state, eigen_branch="master") == "master"

    def test_lite_swarm_uses_integration_branch(self):
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={"1": _epic(1)},
            epic_count=1,
        )
        assert resolve_branch_lite(state) == "feat/P1.E1"

    def test_lite_review_uses_integration_branch(self):
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={
                "1": _epic(1, swarm=_swarm(
                    status="pr_created", pr_number=1,
                    integration_branch="feat/P1.E1",
                )),
            },
            epic_count=1,
        )
        assert resolve_branch_lite(state) == "feat/P1.E1"

    def test_nothing_to_do_returns_empty(self):
        state = _pipeline(lite_plan=_plan(converged=True))
        assert resolve_branch_lite(state) == ""

    def test_swarm_without_branch_falls_back_to_base(self):
        """If integration_branch is missing (bug), fall back to base branch
        rather than returning a broken empty string."""
        epic_data = _epic(1)
        epic_data["lite_swarm"]["integration_branch"] = None
        state = _pipeline(
            lite_plan=_plan(converged=True),
            epics={"1": epic_data},
            epic_count=1,
        )
        assert resolve_branch_lite(state, eigen_branch="main") == "main"


# ---------------------------------------------------------------------------
# Command inventory
# ---------------------------------------------------------------------------

class TestIntegrationBranchCommands:
    def test_swarm_and_review_are_integration_branch_commands(self):
        assert "lite_swarm" in INTEGRATION_BRANCH_COMMANDS_LITE
        assert "lite_review" in INTEGRATION_BRANCH_COMMANDS_LITE

    def test_plan_is_not_an_integration_branch_command(self):
        assert "lite_plan" not in INTEGRATION_BRANCH_COMMANDS_LITE
