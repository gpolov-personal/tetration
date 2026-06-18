"""Permissive next-step inference for eigen-small.

Pure functions, no I/O, fully testable. Operates on the raw dict produced by
``SmallPipelineState.to_dict()``.

Contrast with eigen-squared's ``determine_next`` (and its ``get-context`` gate):
that one HARD-BLOCKS out-of-order execution and refuses to skip a stage. This one
is **permissive** — a stage marked ``skipped`` counts as resolved and we advance;
nothing here ever refuses a skip or reorder. The router owns the decision; this
function only reports the next actionable step from recorded state.
"""

from __future__ import annotations

from typing import Optional

PLANNING_STAGES = ("manifest", "bootstrap", "space_split")
# A stage no longer needs action once it has any resolved outcome — including
# "skipped". This is the permissiveness: skipping is a first-class outcome.
RESOLVED_STAGE_STATUSES = {"reused", "synthesized", "delta", "skipped", "done"}


def determine_next_small(state: dict) -> Optional[tuple[str, dict]]:
    """Return ``(command, context)`` for the next step, or ``None`` when done.

    ``command`` ∈ {``small_route``, ``small_plan``, ``small_build``}.
    """
    shape = state.get("shape", "unknown")
    initiative = state.get("initiative", "")

    # ── Triage not done yet → run the router ──
    if shape in ("unknown", "", None):
        return ("small_route", {"step": "triage", "initiative": initiative})

    # ── Terminal shapes: this pipeline has nothing more to run ──
    if shape == "direct":
        return None  # router already told the operator to implement inline
    if shape == "defer_to_squared":
        return None  # handed off to eigen-squared

    # ── single_phase: walk the planning stages permissively ──
    stages = state.get("stages") or {}
    for stage in PLANNING_STAGES:
        status = (stages.get(stage) or {}).get("status", "pending")
        if status not in RESOLVED_STAGE_STATUSES:
            return ("small_plan", {"next_stage": stage, "initiative": initiative})

    # ── Planning resolved → the wave plan must exist (emitted by space_split) ──
    waves = state.get("waves") or []
    if not waves:
        return (
            "small_plan",
            {"next_stage": "space_split", "note": "emit the wave plan"},
        )

    # ── Walk waves in order: a wave is done when every epic goal is green AND
    #    its review is done. ──
    for wave in waves:
        wid = wave.get("id", "")
        epics = wave.get("epics") or []
        goal_status = wave.get("goal_status") or {}
        review_status = wave.get("review_status", "pending")

        pending = [e for e in epics if goal_status.get(e) != "green"]
        if pending:
            return (
                "small_build",
                {
                    "wave": wid,
                    "parallel": bool(wave.get("parallel", False)),
                    "pending_epics": pending,
                },
            )
        if review_status != "done":
            return ("small_build", {"wave": wid, "step": "review"})
        # else: this wave is fully done — advance.

    return None  # all waves complete
