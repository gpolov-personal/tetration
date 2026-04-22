"""Pipeline state machine — determine the next command to run.

Ported from hooks/pipeline_controller.py (lines 159-456).
Mostly pure functions; the single I/O touch point is a
`swarm-manifest.json` existence probe in the create-issues gate (2.1),
which lets the transition reconcile a stale `manifest_path: null`
against the real filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import PipelineState
from .epic_manifest import load_epic_order


# Commands that run on integration branches (feat/P<N>.E<M>)
INTEGRATION_BRANCH_COMMANDS = {"orchestrate_swarm", "review_swarm_pr"}


def next_for_convergence_pair(
    main_state: dict, deepen_state: dict
) -> tuple[str, str]:
    """Determine next action for a main/deepen command pair.

    Returns:
        ("run_main", reason) | ("run_deepen", reason) | ("converged", reason)
    """
    main_status = main_state.get("status", "not_started")
    main_converged = main_state.get("convergence", {}).get("converged", False)
    main_fc = main_state.get("feedback_consumed", False)
    deepen_status = deepen_state.get("status", "not_started")

    if main_converged:
        return ("converged", "already converged")

    if main_status == "not_started":
        return ("run_main", "first run")

    if deepen_status == "not_started":
        return ("run_deepen", "main completed, deepen not started")

    if not main_fc:
        return ("run_main", "fresh feedback available from deepen")

    return ("run_deepen", "main processed feedback, deepen needs re-analysis")


def next_for_swarm_pair(swarm_state: dict) -> tuple[str, str]:
    """Determine next action for orchestrate_swarm / review_swarm_pr.

    Returns:
        ("run_orchestrate", reason) | ("run_review", reason) | ("converged", reason)
    """
    status = swarm_state.get("status", "not_started")
    converged = swarm_state.get("convergence", {}).get("converged", False)

    if converged:
        return ("converged", "swarm converged")
    if status == "not_started":
        return ("run_orchestrate", "first run")
    if status == "pr_created":
        return ("run_review", "PR ready for review")
    if status == "iterating":
        return ("run_orchestrate", "fixup tasks pending")
    if status == "converged":
        return ("converged", "status says converged (trusting status field)")

    # Unknown status is a data integrity error — do not silently proceed
    return ("converged", f"unknown swarm status '{status}', treating as converged to avoid infinite loop")


def determine_next(
    state: dict,
    eigen_root: str = "",
) -> Optional[tuple[str, dict]]:
    """Walk pipeline state and return the next command + context.

    Args:
        state: Raw pipeline_state.json dict (with "state" top-level key).
        eigen_root: Path to project root (needed for epic_manifest.json loading).

    Returns:
        (command_name, context_dict) or None for human checkpoint / complete.
    """
    s = state.get("state")
    if not s:
        return None

    # ── Initiative level: time_split ↔ deepen_time_split ──

    ts = s.get("time_split")
    dts = s.get("deepen_time_split")
    if not ts or not dts:
        return None

    result = next_for_convergence_pair(ts, dts)
    if result[0] == "run_main":
        return ("time_split", {"scope": "initiative"})
    if result[0] == "run_deepen":
        return ("deepen_time_split", {"scope": "initiative"})

    # Validate phase_count
    try:
        phase_count = int(ts.get("phase_count") or 0)
    except (ValueError, TypeError):
        phase_count = 0
    if phase_count == 0:
        return None

    # ── Per-phase stages ──

    for phase_num in range(1, phase_count + 1):
        phase_key = str(phase_num)
        phase = s.get("phases", {}).get(phase_key)

        if phase is None:
            return None

        phase_review = phase.get("phase_review", {})
        if phase_review.get("status") == "approved":
            continue

        # ── Bootstrap converge (single self-converging command) ──
        # The bootstrap_converge slot MUST exist — it is created by
        # eigen-squared init. Missing key is a data integrity error.
        bc = phase.get("bootstrap_converge")
        if not bc:
            return None  # Data integrity error — cannot proceed without bootstrap_converge state
        if bc.get("status") == "not_started":
            return ("bootstrap_converge", {"scope": "phase", "phase": phase_num})
        if not bc.get("convergence", {}).get("converged", False):
            return ("bootstrap_converge", {"scope": "phase", "phase": phase_num})

        # ── Space split converge (single self-converging command) ──
        # The space_split_converge slot MUST exist — it is created by
        # eigen-squared init. Missing key is a data integrity error.
        ssc = phase.get("space_split_converge")
        if not ssc:
            return None  # Data integrity error — cannot proceed without space_split_converge state
        if ssc.get("status") == "not_started":
            return ("space_split_converge", {"scope": "phase", "phase": phase_num})
        if not ssc.get("convergence", {}).get("converged", False):
            return ("space_split_converge", {"scope": "phase", "phase": phase_num})

        # ── Per-epic stages (sequential: process in order, no dependency checks) ──
        epic_order = load_epic_order(phase_num, eigen_root)
        if not epic_order:
            return ("space_split_converge", {"scope": "phase", "phase": phase_num})

        all_epics_converged = True

        for epic_num in epic_order:
            epic_key = str(epic_num)
            plan = phase.get("plans", {}).get(epic_key)

            # No plan entry → this epic needs planning
            if plan is None:
                return (
                    "plan_epic_converge",
                    {"scope": "epic", "phase": phase_num, "epic": epic_num},
                )

            # ── Plan (single converge command, no pair) ──
            pec = plan.get("plan_epic_converge")
            if not pec or pec.get("status") == "not_started":
                return (
                    "plan_epic_converge",
                    {"scope": "epic", "phase": phase_num, "epic": epic_num},
                )
            pec_converged = pec.get("convergence", {}).get("converged", False)
            if not pec_converged:
                return (
                    "plan_epic_converge",
                    {"scope": "epic", "phase": phase_num, "epic": epic_num},
                )

            # ── Create issues ──
            swarm = plan.get("swarm_execution", {})

            # 2.1 reality-check — reconcile a stale `manifest_path: null`
            # against the actual filesystem. The 2026-04-22 P2.E1
            # regression proved this is required: a squash-merge can
            # land a freshly-created manifest on `$EIGEN_BRANCH` while
            # the pre-merge local snapshot of pipeline_state.json still
            # records `manifest_path: null`, and the stale JSON makes
            # this branch fire again, re-creating the manifest and
            # re-launching the swarm. If the file already exists on
            # disk, treat it as present regardless of what the JSON
            # says — the swarm-pair logic below then routes correctly
            # based on status alone.
            manifest_path = swarm.get("manifest_path")
            if manifest_path is None and eigen_root:
                expected = (
                    Path(eigen_root)
                    / "eigen_initiative"
                    / "phases"
                    / f"phase_{phase_num}"
                    / f"epic_{epic_num}"
                    / "swarm-manifest.json"
                )
                if expected.exists():
                    manifest_path = str(expected.relative_to(eigen_root))

            if manifest_path is None and swarm.get("status") == "not_started":
                return (
                    "create_issues_from_plan_swarm",
                    {"scope": "epic", "phase": phase_num, "epic": epic_num},
                )

            # ── Orchestrate ↔ review ──
            result = next_for_swarm_pair(swarm)
            if result[0] == "run_orchestrate":
                return (
                    "orchestrate_swarm",
                    {
                        "scope": "epic",
                        "phase": phase_num,
                        "epic": epic_num,
                        "branch": swarm.get("integration_branch"),
                    },
                )
            if result[0] == "run_review":
                return (
                    "review_swarm_pr",
                    {
                        "scope": "epic",
                        "phase": phase_num,
                        "epic": epic_num,
                        "branch": swarm.get("integration_branch"),
                    },
                )

            if result[0] != "converged":
                all_epics_converged = False

        # ── All epics in this phase checked ──
        if all_epics_converged:
            # Human checkpoint: phase is done but not yet approved.
            # Status can be "not_started" (needs eigen_continue Mode 1) or
            # "testing" (user is running manual tests, needs eigen_continue Mode 2).
            # Only "approved" allows the pipeline to advance to the next phase.
            if phase_review.get("status") != "approved":
                return None
        else:
            return None

    # All phases approved
    return None


def resolve_branch(
    state: dict,
    eigen_branch: str = "main",
    eigen_root: str = "",
) -> str:
    """Determine which git branch the next command should run on.

    Returns branch name string, or empty string if no action needed.
    """
    result = determine_next(state, eigen_root=eigen_root)
    if result is None:
        return ""

    command, context = result

    if command in INTEGRATION_BRANCH_COMMANDS:
        branch = context.get("branch")
        if branch:
            return branch
        return eigen_branch

    return eigen_branch


def make_context_key(context: dict) -> str:
    """Build a semantic key for retry detection."""
    parts = [context.get("scope", "unknown")]
    if "phase" in context:
        parts.append(f"P{context['phase']}")
    if "epic" in context:
        parts.append(f"E{context['epic']}")
    return ":".join(parts)
