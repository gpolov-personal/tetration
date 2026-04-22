"""Subcommand handlers for eigen-lite CLI.

Each ``cmd_*`` function takes an argparse ``Namespace`` and returns an
exit code (int). ``dispatch()`` routes ``args.command`` to the handler.

Conventions mirrored from eigen-squared:
  - State file path is read from ``--state-file`` if set, else
    ``<EIGEN_ROOT>/<LITE_STATE_RELATIVE_PATH>``.
  - EIGEN_ROOT env var is the default project root.
  - EIGEN_BRANCH is the base branch (default "main").
  - All state mutations go through ``save_state`` (atomic via eigen-core).
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

from ..models_lite import (
    LiteConvergence,
    LiteEpicState,
    LitePipelineState,
    LiteReviewState,
    LiteSwarmExecution,
    SquaredSchemaDetected,
    VALID_LITE_SWARM_STATUSES,
)
from ..state import (
    create_initial_state,
    load_state,
    resolve_state_file,
    save_state,
    validate_state_lite,
)
from ..transitions_lite import (
    determine_next_lite,
    make_context_key_lite,
    resolve_branch_lite,
)


# ---------------------------------------------------------------------------
# Environment + helpers
# ---------------------------------------------------------------------------

def _eigen_root() -> str:
    return os.environ.get("EIGEN_ROOT", "")


def _eigen_branch() -> str:
    return os.environ.get("EIGEN_BRANCH", "main")


def _resolve_state_path(args: Namespace) -> Path:
    explicit = getattr(args, "state_file", None)
    if explicit:
        return Path(explicit)
    root = _eigen_root()
    if not root:
        print(
            "ERROR: EIGEN_ROOT not set and --state-file not provided",
            file=sys.stderr,
        )
        sys.exit(1)
    return resolve_state_file(root)


def _load_or_die(args: Namespace) -> tuple[LitePipelineState, Path]:
    path = _resolve_state_path(args)
    try:
        state = load_state(path)
    except SquaredSchemaDetected as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    if state is None:
        print(f"ERROR: state file not found at {path}", file=sys.stderr)
        sys.exit(1)
    return state, path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_epic(
    state: LitePipelineState, epic: int
) -> LiteEpicState:
    key = str(epic)
    if key not in state.epics:
        print(f"ERROR: no epic E{epic} in state", file=sys.stderr)
        sys.exit(1)
    return state.epics[key]


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def cmd_init(args: Namespace) -> int:
    path = _resolve_state_path(args)
    if path.exists() and not getattr(args, "force", False):
        print(f"ERROR: {path} already exists; pass --force to overwrite",
              file=sys.stderr)
        return 1
    state = create_initial_state(args.feature_set, epic_count=args.epic_count)
    save_state(state, path)
    print(json.dumps({
        "status": "initialized",
        "state_file": str(path),
        "feature_set": args.feature_set,
        "epic_count": args.epic_count,
    }))
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    summary = _status_summary(state)
    if getattr(args, "as_json", False):
        print(json.dumps(summary, indent=2))
    else:
        print(f"Feature set: {state.feature_set}")
        print(f"Plan: {summary['plan']['status']} "
              f"(converged={summary['plan']['converged']}, "
              f"stages={summary['plan']['stages_completed']})")
        print(f"Epics: {len(state.epics)}")
        for key in sorted(state.epics.keys(), key=int):
            info = summary["epics"][key]
            print(f"  E{key}: swarm={info['swarm_status']} "
                  f"review={info['review_status']} "
                  f"converged={info['converged']}")
    return 0


def _status_summary(state: LitePipelineState) -> dict:
    return {
        "feature_set": state.feature_set,
        "epic_count": state.epic_count,
        "plan": {
            "status": state.lite_plan.status,
            "converged": state.lite_plan.convergence.converged,
            "stages_completed": list(state.lite_plan.stages_completed),
        },
        "epics": {
            key: {
                "swarm_status": epic.lite_swarm.status,
                "review_status": epic.lite_review.status,
                "converged": epic.lite_swarm.convergence.converged,
                "pr_number": epic.lite_swarm.pr_number,
                "integration_branch": epic.lite_swarm.integration_branch,
                "is_e2e_epic": epic.is_e2e_epic,
            }
            for key, epic in state.epics.items()
        },
    }


# ---------------------------------------------------------------------------
# next
# ---------------------------------------------------------------------------

def cmd_next(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    result = determine_next_lite(state.to_dict())
    if result is None:
        output = {"status": "complete", "command": None, "context": None}
    else:
        command, context = result
        output = {"status": "ready", "command": command, "context": context}

    if getattr(args, "as_json", False):
        print(json.dumps(output))
    else:
        if result is None:
            print("Pipeline complete — no next command.")
        else:
            command, context = result
            print(f"Next: {command} {context}")
    return 0


# ---------------------------------------------------------------------------
# get-context
# ---------------------------------------------------------------------------

def cmd_get_context(args: Namespace) -> int:
    """Return a JSON blob with context needed to start a given command."""
    state, _ = _load_or_die(args)
    target = args.target_command

    context: dict = {"command": target, "feature_set": state.feature_set}

    if target == "lite_plan":
        context["scope"] = "initiative"
        context["stages_completed"] = list(
            state.lite_plan.stages_completed
        )
        context["output_paths"] = dict(state.lite_plan.output_paths)
        context["iteration"] = state.lite_plan.iteration

    elif target in ("lite_swarm", "lite_review"):
        if args.epic is None:
            print(f"ERROR: --epic required for {target}", file=sys.stderr)
            return 1
        epic = _get_epic(state, args.epic)
        context["scope"] = "epic"
        context["epic"] = args.epic
        context["branch"] = epic.lite_swarm.integration_branch
        context["manifest_path"] = epic.swarm_manifest
        context["epic_path"] = epic.epic_path
        context["epic_file"] = epic.epic_file
        context["plan_file"] = epic.plan_file
        context["is_e2e_epic"] = epic.is_e2e_epic
        context["swarm_status"] = epic.lite_swarm.status
        context["pr_url"] = epic.lite_swarm.pr_url
        context["pr_number"] = epic.lite_swarm.pr_number
        context["review_iteration"] = epic.lite_review.review_iteration

    else:
        print(f"ERROR: unknown target command {target!r}", file=sys.stderr)
        return 1

    print(json.dumps(context))
    return 0


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------

def cmd_complete(args: Namespace) -> int:
    state, path = _load_or_die(args)
    target = args.target_command

    if target == "lite_plan":
        plan = state.lite_plan
        plan.status = "completed"
        plan.iteration += 1
        if getattr(args, "stage", None):
            if args.stage not in plan.stages_completed:
                plan.stages_completed.append(args.stage)
        if getattr(args, "output_paths", None):
            try:
                plan.output_paths.update(json.loads(args.output_paths))
            except json.JSONDecodeError as exc:
                print(f"ERROR: --output-paths not valid JSON: {exc}",
                      file=sys.stderr)
                return 1
        if getattr(args, "converged", False):
            plan.convergence = LiteConvergence(
                converged=True,
                decided_by=getattr(args, "decided_by", None) or "lite_plan",
                decided_at=_now_iso(),
                reason=getattr(args, "reason", None) or "stages complete",
            )

    elif target in ("lite_swarm", "lite_review"):
        if args.epic is None:
            print(f"ERROR: --epic required for {target}", file=sys.stderr)
            return 1
        epic = _get_epic(state, args.epic)
        if target == "lite_swarm":
            _apply_swarm_complete(epic.lite_swarm, args)
        else:
            _apply_review_complete(epic.lite_review, args)

    else:
        print(f"ERROR: unknown target command {target!r}", file=sys.stderr)
        return 1

    save_state(state, path)
    print(json.dumps({"status": "ok", "target": target}))
    return 0


def _apply_swarm_complete(swarm: LiteSwarmExecution, args: Namespace) -> None:
    if getattr(args, "pr_url", None):
        swarm.pr_url = args.pr_url
    if getattr(args, "pr_number", None) is not None:
        swarm.pr_number = args.pr_number
    if getattr(args, "integration_branch", None):
        swarm.integration_branch = args.integration_branch
    if swarm.status == "not_started" and swarm.pr_number:
        swarm.status = "pr_created"


def _apply_review_complete(review: LiteReviewState, args: Namespace) -> None:
    review.review_iteration += 1
    review.status = "complete"
    if getattr(args, "report_path", None):
        if args.report_path not in review.review_reports:
            review.review_reports.append(args.report_path)
    if getattr(args, "findings_summary", None):
        try:
            review.findings_summary.update(
                json.loads(args.findings_summary)
            )
        except json.JSONDecodeError as exc:
            print(f"ERROR: --findings-summary not valid JSON: {exc}",
                  file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# mark-converged
# ---------------------------------------------------------------------------

def cmd_mark_converged(args: Namespace) -> int:
    state, path = _load_or_die(args)
    target = args.target_command
    reason = args.reason

    conv = LiteConvergence(
        converged=True,
        decided_by=target,
        decided_at=_now_iso(),
        reason=reason,
    )

    if target == "lite_plan":
        state.lite_plan.convergence = conv
        state.lite_plan.status = "completed"
    elif target == "lite_swarm":
        if args.epic is None:
            print("ERROR: --epic required for lite_swarm", file=sys.stderr)
            return 1
        epic = _get_epic(state, args.epic)
        epic.lite_swarm.convergence = conv
        epic.lite_swarm.status = "converged"
    elif target == "lite_review":
        if args.epic is None:
            print("ERROR: --epic required for lite_review", file=sys.stderr)
            return 1
        epic = _get_epic(state, args.epic)
        epic.lite_review.convergence = conv
        epic.lite_review.status = "complete"
    else:
        print(f"ERROR: unknown target command {target!r}", file=sys.stderr)
        return 1

    save_state(state, path)
    print(json.dumps({"status": "converged", "target": target,
                       "reason": reason}))
    return 0


# ---------------------------------------------------------------------------
# set-swarm-status
# ---------------------------------------------------------------------------

def cmd_set_swarm_status(args: Namespace) -> int:
    if args.status_value not in VALID_LITE_SWARM_STATUSES:
        print(f"ERROR: invalid swarm status {args.status_value!r}; "
              f"valid: {sorted(VALID_LITE_SWARM_STATUSES)}", file=sys.stderr)
        return 1

    state, path = _load_or_die(args)
    epic = _get_epic(state, args.epic)
    swarm = epic.lite_swarm
    swarm.status = args.status_value

    if args.status_value == "converged":
        swarm.convergence = LiteConvergence(
            converged=True,
            decided_by="set-swarm-status",
            decided_at=_now_iso(),
            reason="manual status update",
        )

    if getattr(args, "pr_url", None):
        swarm.pr_url = args.pr_url
    if getattr(args, "pr_number", None) is not None:
        swarm.pr_number = args.pr_number
    if getattr(args, "integration_branch", None):
        swarm.integration_branch = args.integration_branch

    save_state(state, path)
    print(json.dumps({"status": "ok", "epic": args.epic,
                       "swarm_status": args.status_value}))
    return 0


# ---------------------------------------------------------------------------
# add-review-report
# ---------------------------------------------------------------------------

def cmd_add_review_report(args: Namespace) -> int:
    state, path = _load_or_die(args)
    epic = _get_epic(state, args.epic)
    if args.report_path not in epic.lite_review.review_reports:
        epic.lite_review.review_reports.append(args.report_path)
    if epic.lite_review.status == "not_started":
        epic.lite_review.status = "in_progress"
    save_state(state, path)
    print(json.dumps({
        "status": "ok",
        "epic": args.epic,
        "review_reports": list(epic.lite_review.review_reports),
    }))
    return 0


# ---------------------------------------------------------------------------
# init-epics
# ---------------------------------------------------------------------------

def cmd_init_epics(args: Namespace) -> int:
    """Populate state.epics from a list produced by lite_plan Stage D.

    Input JSON shape:
        [
          {"epic": 1, "is_e2e_epic": false},
          {"epic": 2, "is_e2e_epic": false},
          {"epic": 3, "is_e2e_epic": true}
        ]
    """
    state, path = _load_or_die(args)

    try:
        epics_meta = json.loads(args.epics_json)
    except json.JSONDecodeError as exc:
        print(f"ERROR: --epics not valid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(epics_meta, list) or not epics_meta:
        print("ERROR: --epics must be a non-empty JSON list", file=sys.stderr)
        return 1

    new_epics: dict[str, LiteEpicState] = {}
    for entry in epics_meta:
        if not isinstance(entry, dict) or "epic" not in entry:
            print(f"ERROR: each entry needs an 'epic' key; got {entry!r}",
                  file=sys.stderr)
            return 1
        num = int(entry["epic"])
        key = str(num)
        is_e2e = bool(entry.get("is_e2e_epic", False))
        new_epics[key] = LiteEpicState(
            epic_path=f"phases/phase_1/epic_{num}/",
            epic_file=f"phases/phase_1/epic_{num}/epic.md",
            plan_file=f"phases/phase_1/epic_{num}/plan.md",
            swarm_manifest=f"phases/phase_1/epic_{num}/swarm-manifest.json",
            is_e2e_epic=is_e2e,
            lite_swarm=LiteSwarmExecution(
                integration_branch=f"feat/P1.E{num}",
            ),
        )

    state.epics = new_epics
    state.epic_count = len(new_epics)
    save_state(state, path)
    print(json.dumps({
        "status": "ok",
        "epic_count": state.epic_count,
        "epics": sorted(state.epics.keys(), key=int),
    }))
    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def cmd_validate(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    errors = validate_state_lite(state)
    if not errors:
        print(json.dumps({"valid": True, "errors": []}))
        return 0
    print(json.dumps({"valid": False, "errors": errors}, indent=2))
    return 1


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "init": cmd_init,
    "status": cmd_status,
    "next": cmd_next,
    "get-context": cmd_get_context,
    "complete": cmd_complete,
    "mark-converged": cmd_mark_converged,
    "set-swarm-status": cmd_set_swarm_status,
    "add-review-report": cmd_add_review_report,
    "init-epics": cmd_init_epics,
    "validate": cmd_validate,
}


def register_handler(name: str, handler) -> None:
    """Used by plumbing handlers (Batch C) to extend the dispatch table."""
    _HANDLERS[name] = handler


def dispatch(args: Namespace) -> int:
    handler = _HANDLERS.get(args.command)
    if handler is None:
        print(f"ERROR: unknown command {args.command!r}", file=sys.stderr)
        return 1
    return handler(args)
