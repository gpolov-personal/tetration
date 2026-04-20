"""Pipeline state machine for eigen-lite — determine the next command to run.

Pure functions: no I/O, no side effects, fully testable. Operates on the raw
dict produced by ``LitePipelineState.to_dict`` (or loaded directly via
``eigen_core.cli.state_io.load_raw_state``).

Contract mirrors squared's ``determine_next`` but walks a flat single-phase
state (``lite_plan`` + ``epics`` dict) instead of the nested phase/epic tree.
"""

from __future__ import annotations

from typing import Optional


INTEGRATION_BRANCH_COMMANDS_LITE = {"lite_swarm", "lite_review"}


def make_context_key_lite(context: dict) -> str:
    """Build a semantic retry-detection key for a context.

    Unlike squared (initiative/phase/epic), lite has only two scopes:
    ``initiative`` (for lite_plan) and ``epic`` (for lite_swarm/lite_review).
    """
    scope = context.get("scope", "unknown")
    if scope == "initiative":
        return "initiative"
    if "epic" in context:
        return f"{scope}:E{context['epic']}"
    return scope


def determine_next_lite(state: dict) -> Optional[tuple[str, dict]]:
    """Walk the lite pipeline state and return the next command + context.

    Returns ``None`` when the pipeline is complete or when state is malformed
    enough that no action can be safely inferred.
    """
    s = state.get("state")
    if not s:
        return None

    # ── Stage 1: lite_plan must converge before any epic work starts ──
    plan = s.get("lite_plan") or {}
    if not plan.get("convergence", {}).get("converged"):
        return (
            "lite_plan",
            {
                "scope": "initiative",
                "feature_set": state.get("feature_set", ""),
            },
        )

    # ── Stage 2: walk epics in numeric order ──
    epics = s.get("epics") or {}

    def _epic_sort_key(k: str) -> int:
        try:
            return int(k)
        except (ValueError, TypeError):
            return 10 ** 9  # non-numeric keys sort last, defensively

    for epic_key in sorted(epics.keys(), key=_epic_sort_key):
        epic = epics[epic_key] or {}
        swarm = epic.get("lite_swarm") or {}
        review = epic.get("lite_review") or {}

        try:
            epic_num = int(epic_key)
        except (ValueError, TypeError):
            continue  # can't act on non-numeric epic ids

        swarm_status = swarm.get("status", "not_started")
        swarm_converged = swarm.get("convergence", {}).get("converged", False)
        review_converged = review.get("convergence", {}).get("converged", False)

        # Epic fully done → advance to next
        if swarm_converged or (swarm_status == "converged"):
            continue

        # Review converged but swarm not yet marked — caller will mark on
        # auto-merge. Move on so we don't spin.
        if review_converged:
            continue

        integration_branch = swarm.get("integration_branch")

        # Need to run lite_swarm (first time OR fixup iteration — lite_review
        # flipped status to "iterating" after finding P1/P2, so the swarm has
        # to execute the new fixup tasks before the next review)
        if swarm_status in ("not_started", "iterating"):
            return (
                "lite_swarm",
                {
                    "scope": "epic",
                    "epic": epic_num,
                    "branch": integration_branch,
                    "manifest_path": epic.get("swarm_manifest"),
                },
            )

        # PR exists, no outstanding fixups → review is next
        if swarm_status == "pr_created":
            return (
                "lite_review",
                {
                    "scope": "epic",
                    "epic": epic_num,
                    "branch": integration_branch,
                    "pr_number": swarm.get("pr_number"),
                },
            )

        # Unknown swarm status — treat as no-op rather than loop forever
        continue

    # All epics processed — pipeline complete
    return None


def resolve_branch_lite(state: dict, eigen_branch: str = "main") -> str:
    """Determine which git branch the next command should run on.

    Returns:
        branch name, or empty string if there's nothing to do.
    """
    result = determine_next_lite(state)
    if result is None:
        return ""

    command, context = result

    if command in INTEGRATION_BRANCH_COMMANDS_LITE:
        branch = context.get("branch")
        if branch:
            return branch
        # Fall back to base branch rather than empty string — a swarm without
        # an integration_branch is a bug, but breaking the watchdog with ""
        # loses observability.
        return eigen_branch

    return eigen_branch
