"""Subcommand dispatch."""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

from ..models import (
    EpicPlan,
    PipelineState,
    Recommendation,
    RECOMMENDATION_MATRIX,
    MAX_RECOMMENDATIONS_PER_PAIR,
    VALID_SWARM_STATUSES,
)
from ..state import (
    create_initial_state,
    load_state,
    resolve_state_file,
    save_state,
    validate_state,
)
from ..transitions import determine_next, make_context_key, resolve_branch
from ..scheduler import (
    check_retry,
    log_entry as sched_log_entry,
    resolve_hook_log,
    schedule_command,
    COMMAND_TO_SKILL,
)
from .. import git_ops


def _eigen_root() -> str:
    return os.environ.get("EIGEN_ROOT", "")


def _eigen_branch() -> str:
    return os.environ.get("EIGEN_BRANCH", "main")


def _state_file(args: Namespace) -> Path:
    if hasattr(args, "state_file") and args.state_file:
        return Path(args.state_file)
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        sys.exit(1)
    return resolve_state_file(root)


def _load_or_die(args: Namespace) -> tuple[PipelineState, Path]:
    sf = _state_file(args)
    state = load_state(sf)
    if state is None:
        print(f"ERROR: Cannot load {sf}", file=sys.stderr)
        sys.exit(1)
    return state, sf


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Maps main commands to their deepen counterparts
MAIN_TO_DEEPEN = {
    "time_split": "deepen_time_split",
    "bootstrap": "deepen_bootstrap",
    "space_split": "deepen_space_split",
    "plan_phase_epic": "deepen_plan_phase_epic",
}

DEEPEN_TO_MAIN = {v: k for k, v in MAIN_TO_DEEPEN.items()}

# Which commands are "deepen" commands
DEEPEN_COMMANDS = set(DEEPEN_TO_MAIN.keys())

# Which commands are "main" commands (convergence pair left side)
MAIN_COMMANDS = set(MAIN_TO_DEEPEN.keys())


def dispatch(args: Namespace) -> int:
    """Route to the appropriate subcommand handler."""
    handlers = {
        "init": cmd_init,
        "status": cmd_status,
        "next": cmd_next,
        "get-context": cmd_get_context,
        "complete": cmd_complete,
        "mark-converged": cmd_mark_converged,
        "add-recommendation": cmd_add_recommendation,
        "clear-recommendations": cmd_clear_recommendations,
        "set-swarm-status": cmd_set_swarm_status,
        "add-review-report": cmd_add_review_report,
        "init-plan": cmd_init_plan,
        "set-phase-review": cmd_set_phase_review,
        "commit-state": cmd_commit_state,
        "sync": cmd_sync,
        "resolve-branch": cmd_resolve_branch,
        "checkout-branch": cmd_checkout_branch,
        "schedule-next": cmd_schedule_next,
        "validate": cmd_validate,
        "install": cmd_install,
    }
    handler = handlers.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1
    return handler(args)


# ─────────────────────────────────────────────────────────────────────────────
# SUBCOMMAND IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────────────────────


def cmd_init(args: Namespace) -> int:
    sf = _state_file(args)
    if sf.exists():
        print(f"ERROR: {sf} already exists. Delete it first to re-initialize.", file=sys.stderr)
        return 1
    state = create_initial_state(args.initiative, args.phase_count)
    save_state(state, sf)
    print(json.dumps({"status": "created", "state_file": str(sf), "phase_count": args.phase_count}))
    return 0


def cmd_status(args: Namespace) -> int:
    state, _ = _load_or_die(args)

    if getattr(args, "as_json", False):
        print(json.dumps(state.to_dict(), indent=2))
        return 0

    print(f"Pipeline: {state.initiative} (schema {state.schema_version})")
    print(f"Updated: {state.updated_at or 'never'}")
    print()

    ts = state.time_split
    dts = state.deepen_time_split
    conv = "converged" if ts.convergence.converged else ts.status
    print(f"  time_split          {conv:12s}  iter {ts.iteration}")
    print(f"  deepen_time_split   {dts.status:12s}  iter {dts.iteration}")
    print()

    for pk in sorted(state.phases.keys(), key=int):
        phase = state.phases[pk]
        print(f"Phase {pk}:")
        bs = phase.bootstrap
        bconv = "converged" if bs.convergence.converged else bs.status
        print(f"  bootstrap           {bconv:12s}  iter {bs.iteration}")
        dbs = phase.deepen_bootstrap
        print(f"  deepen_bootstrap    {dbs.status:12s}  iter {dbs.iteration}")
        ss = phase.space_split
        sconv = "converged" if ss.convergence.converged else ss.status
        print(f"  space_split         {sconv:12s}  iter {ss.iteration}")
        dss = phase.deepen_space_split
        print(f"  deepen_space_split  {dss.status:12s}  iter {dss.iteration}")

        for ek in sorted(phase.plans.keys(), key=lambda x: int(x)):
            ep = phase.plans[ek]
            pconv = "converged" if ep.plan_phase_epic.convergence.converged else ep.plan_phase_epic.status
            sw = ep.swarm_execution
            sconv = "converged" if sw.convergence.converged else sw.status
            print(f"  P{pk}.E{ek} plan       {pconv:12s}  swarm: {sconv:12s}  review_iter: {sw.review_iteration}")

        pr = phase.phase_review
        print(f"  phase_review        {pr.status}")
        print()

    # Show next command
    raw = state.to_dict()
    result = determine_next(raw, eigen_root=_eigen_root())
    if result:
        cmd, ctx = result
        print(f"Next: {cmd} ({ctx})")
    else:
        print("Next: none (human checkpoint or complete)")
    return 0


def cmd_next(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    raw = state.to_dict()
    result = determine_next(raw, eigen_root=_eigen_root())

    if result is None:
        if getattr(args, "as_json", False):
            print(json.dumps({"command": None, "context": None}))
        else:
            print("No next command (human checkpoint or pipeline complete)")
        return 0

    cmd, ctx = result
    branch = resolve_branch(raw, eigen_branch=_eigen_branch(), eigen_root=_eigen_root())
    ctx["branch"] = branch

    if getattr(args, "as_json", False):
        print(json.dumps({"command": cmd, "context": ctx}))
    else:
        print(f"{cmd}")
        for k, v in ctx.items():
            print(f"  {k}: {v}")
    return 0


def cmd_get_context(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    cmd = args.target_command
    phase = args.phase
    epic = args.epic

    # Auto-detect phase/epic from next if not provided
    if phase is None:
        raw = state.to_dict()
        result = determine_next(raw, eigen_root=_eigen_root())
        if result and result[0] == cmd:
            ctx = result[1]
            phase = ctx.get("phase")
            epic = epic or ctx.get("epic")

    if phase is None and cmd not in ("time_split", "deepen_time_split"):
        print(f"ERROR: --phase required for {cmd}", file=sys.stderr)
        return 1

    context: dict = {"command": cmd, "phase": phase, "epic": epic}

    # Build command-specific context
    if cmd in ("time_split", "deepen_time_split"):
        ts = state.time_split
        dts = state.deepen_time_split

        if cmd == "time_split":
            if ts.convergence.converged:
                print("ERROR: time_split already converged", file=sys.stderr)
                return 1
            context["iteration"] = ts.iteration + 1
            context["is_first_run"] = ts.iteration == 0
            context["should_process_feedback"] = (
                ts.iteration >= 1 and not ts.feedback_consumed
            )
            if dts.feedback_path:
                context["feedback_path"] = dts.feedback_path
            context["output_paths"] = ts.output_paths
            recs = state.recommendations.get("time_split", [])
            context["recommendations"] = [
                r.to_dict() if hasattr(r, "to_dict") else r for r in recs
            ]
        else:  # deepen_time_split
            if ts.convergence.converged:
                print("ERROR: time_split already converged, no deepen needed", file=sys.stderr)
                return 1
            context["iteration"] = dts.iteration + 1
            context["previous_feedback_path"] = dts.feedback_path
            context["previous_feedback_exists"] = dts.feedback_path is not None
            context["main_command_outputs"] = ts.output_paths
            context["lessons_dir"] = "eigen_lessons/time_split/"

    elif cmd in MAIN_COMMANDS:
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ph = state.phases[pk]

        if cmd == "bootstrap":
            ms = ph.bootstrap
            ds = ph.deepen_bootstrap
        elif cmd == "space_split":
            ms = ph.space_split
            ds = ph.deepen_space_split
        elif cmd == "plan_phase_epic":
            if epic is None:
                print("ERROR: --epic required for plan_phase_epic", file=sys.stderr)
                return 1
            ek = str(epic)
            if ek not in ph.plans:
                context["is_first_run"] = True
                context["iteration"] = 1
            else:
                ms = ph.plans[ek].plan_phase_epic
                ds = ph.plans[ek].deepen_plan_phase_epic
                if ms.convergence.converged:
                    print(f"ERROR: plan P{phase}.E{epic} already converged", file=sys.stderr)
                    return 1
                context["iteration"] = ms.iteration + 1
                context["is_first_run"] = ms.iteration == 0
                context["should_process_feedback"] = ms.iteration >= 1 and not ms.feedback_consumed
                if ds.feedback_path:
                    context["feedback_path"] = ds.feedback_path
                context["output_paths"] = ms.output_paths
            recs = [
                r.to_dict() if hasattr(r, "to_dict") else r
                for r in state.recommendations.get(cmd, [])
                if (isinstance(r, dict) and r.get("phase") in (phase, None))
                or (hasattr(r, "phase") and r.phase in (phase, None))
            ]
            context["recommendations"] = recs
            print(json.dumps(context, indent=2) if getattr(args, "as_json", False) else str(context))
            return 0

        if ms.convergence.converged:
            print(f"ERROR: {cmd} phase {phase} already converged", file=sys.stderr)
            return 1
        context["iteration"] = ms.iteration + 1
        context["is_first_run"] = ms.iteration == 0
        context["should_process_feedback"] = ms.iteration >= 1 and not ms.feedback_consumed
        if ds.feedback_path:
            context["feedback_path"] = ds.feedback_path
        context["output_paths"] = ms.output_paths
        recs = [
            r.to_dict() if hasattr(r, "to_dict") else r
            for r in state.recommendations.get(cmd, [])
            if (isinstance(r, dict) and r.get("phase") in (phase, None))
            or (hasattr(r, "phase") and r.phase in (phase, None))
        ]
        context["recommendations"] = recs

    elif cmd in DEEPEN_COMMANDS:
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ph = state.phases[pk]
        main_cmd = DEEPEN_TO_MAIN[cmd]

        if cmd == "deepen_bootstrap":
            ms = ph.bootstrap
            ds = ph.deepen_bootstrap
        elif cmd == "deepen_space_split":
            ms = ph.space_split
            ds = ph.deepen_space_split
        elif cmd == "deepen_plan_phase_epic":
            if epic is None:
                print("ERROR: --epic required for deepen_plan_phase_epic", file=sys.stderr)
                return 1
            ek = str(epic)
            if ek not in ph.plans:
                print(f"ERROR: Plan P{phase}.E{epic} not found", file=sys.stderr)
                return 1
            ms = ph.plans[ek].plan_phase_epic
            ds = ph.plans[ek].deepen_plan_phase_epic

        if ms.convergence.converged:
            print(f"ERROR: {main_cmd} already converged, no deepen needed", file=sys.stderr)
            return 1
        context["iteration"] = ds.iteration + 1
        context["previous_feedback_path"] = ds.feedback_path
        context["previous_feedback_exists"] = ds.feedback_path is not None
        context["main_command_outputs"] = ms.output_paths
        context["lessons_dir"] = f"eigen_lessons/{main_cmd}/"

    elif cmd in ("create_issues_from_plan_swarm", "orchestrate_swarm", "review_swarm_pr"):
        if phase is None or epic is None:
            print(f"ERROR: --phase and --epic required for {cmd}", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        if pk not in state.phases or ek not in state.phases[pk].plans:
            print(f"ERROR: Plan P{phase}.E{epic} not found", file=sys.stderr)
            return 1
        sw = state.phases[pk].plans[ek].swarm_execution
        context["branch"] = sw.integration_branch or git_ops.integration_branch_name(phase, epic)
        context["manifest_path"] = sw.manifest_path
        context["swarm_status"] = sw.status
        context["review_iteration"] = sw.review_iteration
        context["pr_number"] = sw.pr_number
        context["pr_url"] = sw.pr_url

    if getattr(args, "as_json", False):
        print(json.dumps(context, indent=2))
    else:
        for k, v in context.items():
            print(f"  {k}: {v}")
    return 0


def cmd_complete(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    cmd = args.target_command
    phase = args.phase
    epic = args.epic
    now = _now()

    if cmd == "time_split":
        ts = state.time_split
        ts.status = "completed"
        ts.iteration += 1
        ts.last_run_at = now
        ts.feedback_consumed = True
        state.deepen_time_split.feedback_consumed = True
        if args.phase_count is not None:
            ts.phase_count = args.phase_count
            # Initialize new phases if count increased
            for i in range(1, args.phase_count + 1):
                pk = str(i)
                if pk not in state.phases:
                    from ..models import PhaseState
                    state.phases[pk] = PhaseState()
        if args.output_paths:
            ts.output_paths = json.loads(args.output_paths)
        elif args.output_path:
            ts.output_paths["initiative_summary"] = args.output_path

    elif cmd == "deepen_time_split":
        dts = state.deepen_time_split
        dts.status = "completed"
        dts.iteration += 1
        dts.last_run_at = now
        dts.feedback_consumed = False
        state.time_split.feedback_consumed = False
        if args.feedback_path:
            dts.feedback_path = args.feedback_path
        if args.findings_summary:
            from ..models import FindingsSummary
            fs = json.loads(args.findings_summary)
            dts.findings_summary = FindingsSummary.from_dict(fs)

    elif cmd in MAIN_COMMANDS and phase is not None:
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ph = state.phases[pk]

        if cmd == "bootstrap":
            ms, ds = ph.bootstrap, ph.deepen_bootstrap
        elif cmd == "space_split":
            ms, ds = ph.space_split, ph.deepen_space_split
        elif cmd == "plan_phase_epic":
            if epic is None:
                print("ERROR: --epic required", file=sys.stderr)
                return 1
            ek = str(epic)
            if ek not in ph.plans:
                ph.plans[ek] = EpicPlan()
            ms = ph.plans[ek].plan_phase_epic
            ds = ph.plans[ek].deepen_plan_phase_epic

        ms.status = "completed"
        ms.iteration += 1
        ms.last_run_at = now
        ms.feedback_consumed = True
        ds.feedback_consumed = True

        if cmd == "bootstrap" and args.output_path:
            ms.output_paths["bootstrap_report"] = args.output_path
            ms.output_paths["target_repo"] = _eigen_root()
        elif cmd == "space_split":
            if args.epic_dag:
                ms.output_paths["epic_dag"] = args.epic_dag
            if args.e2e_config:
                ms.output_paths["phase_e2e_config"] = args.e2e_config
            if args.epic_ids:
                ms.output_paths["epic_ids"] = json.loads(args.epic_ids)
        elif cmd == "plan_phase_epic" and args.plan_file:
            ms.output_paths["plan_file"] = args.plan_file

    elif cmd in DEEPEN_COMMANDS and phase is not None:
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ph = state.phases[pk]
        main_cmd = DEEPEN_TO_MAIN[cmd]

        if cmd == "deepen_bootstrap":
            ms, ds = ph.bootstrap, ph.deepen_bootstrap
        elif cmd == "deepen_space_split":
            ms, ds = ph.space_split, ph.deepen_space_split
        elif cmd == "deepen_plan_phase_epic":
            if epic is None:
                print("ERROR: --epic required", file=sys.stderr)
                return 1
            ek = str(epic)
            if ek not in ph.plans:
                print(f"ERROR: Plan P{phase}.E{epic} not found", file=sys.stderr)
                return 1
            ms = ph.plans[ek].plan_phase_epic
            ds = ph.plans[ek].deepen_plan_phase_epic

        ds.status = "completed"
        ds.iteration += 1
        ds.last_run_at = now
        ds.feedback_consumed = False
        ms.feedback_consumed = False

        if args.feedback_path:
            ds.feedback_path = args.feedback_path
        if args.findings_summary:
            from ..models import FindingsSummary
            fs = json.loads(args.findings_summary)
            ds.findings_summary = FindingsSummary.from_dict(fs)

    elif cmd == "create_issues_from_plan_swarm":
        if phase is None or epic is None:
            print("ERROR: --phase and --epic required", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ph = state.phases[pk]
        if ek not in ph.plans:
            ph.plans[ek] = EpicPlan()
        sw = ph.plans[ek].swarm_execution
        if args.manifest_path:
            sw.manifest_path = args.manifest_path
        if args.integration_branch:
            sw.integration_branch = args.integration_branch

    elif cmd == "orchestrate_swarm":
        if phase is None or epic is None:
            print("ERROR: --phase and --epic required", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        sw = state.phases[pk].plans[ek].swarm_execution
        sw.status = "pr_created"
        sw.completed_at = now
        if args.pr_url:
            sw.pr_url = args.pr_url
        if args.pr_number:
            sw.pr_number = args.pr_number

    elif cmd == "review_swarm_pr":
        if phase is None or epic is None:
            print("ERROR: --phase and --epic required", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        sw = state.phases[pk].plans[ek].swarm_execution
        sw.review_iteration += 1
        sw.status = "iterating"
        if args.report_path:
            sw.review_reports.append(args.report_path)
        if args.findings_summary:
            sw.findings_summary = json.loads(args.findings_summary)

    else:
        print(f"ERROR: Unknown command or missing --phase: {cmd}", file=sys.stderr)
        return 1

    save_state(state, sf)
    print(json.dumps({"status": "completed", "command": cmd}))
    return 0


def cmd_mark_converged(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    cmd = args.target_command
    phase = args.phase
    epic = args.epic
    now = _now()

    # Determine caller (which deepen command is marking convergence)
    if cmd == "time_split":
        caller = "deepen_time_split"
        target = state.time_split
    elif cmd == "bootstrap" and phase is not None:
        caller = "deepen_bootstrap"
        target = state.phases[str(phase)].bootstrap
    elif cmd == "space_split" and phase is not None:
        caller = "deepen_space_split"
        target = state.phases[str(phase)].space_split
    elif cmd == "plan_phase_epic" and phase is not None and epic is not None:
        caller = "deepen_plan_phase_epic"
        target = state.phases[str(phase)].plans[str(epic)].plan_phase_epic
    elif cmd == "swarm_execution" and phase is not None and epic is not None:
        caller = "review_swarm_pr"
        sw = state.phases[str(phase)].plans[str(epic)].swarm_execution
        sw.convergence.converged = True
        sw.convergence.decided_by = caller
        sw.convergence.decided_at = now
        sw.convergence.reason = args.reason
        sw.status = "converged"
        save_state(state, sf)
        print(json.dumps({"status": "converged", "command": cmd, "decided_by": caller}))
        return 0
    else:
        print(f"ERROR: Cannot converge {cmd} with given args", file=sys.stderr)
        return 1

    target.convergence.converged = True
    target.convergence.decided_by = caller
    target.convergence.decided_at = now
    target.convergence.reason = args.reason

    save_state(state, sf)
    print(json.dumps({"status": "converged", "command": cmd, "decided_by": caller}))
    return 0


def cmd_add_recommendation(args: Namespace) -> int:
    state, sf = _load_or_die(args)

    allowed_targets = RECOMMENDATION_MATRIX.get(args.from_cmd)
    if allowed_targets is None:
        print(f"ERROR: {args.from_cmd} is not a valid recommendation source", file=sys.stderr)
        return 1
    if args.target not in allowed_targets:
        print(f"ERROR: {args.from_cmd} cannot recommend to {args.target}", file=sys.stderr)
        return 1

    if args.target not in state.recommendations:
        state.recommendations[args.target] = []

    # Check limit
    existing = [
        r for r in state.recommendations[args.target]
        if (isinstance(r, dict) and r.get("from") == args.from_cmd)
        or (hasattr(r, "from_cmd") and r.from_cmd == args.from_cmd)
    ]
    if len(existing) >= MAX_RECOMMENDATIONS_PER_PAIR:
        print(f"WARNING: Max {MAX_RECOMMENDATIONS_PER_PAIR} recommendations from {args.from_cmd} to {args.target}", file=sys.stderr)
        return 1

    rec = Recommendation(
        from_cmd=args.from_cmd,
        at_iteration=args.iteration,
        phase=args.phase,
        epic=args.epic,
        text=args.text,
    )
    state.recommendations[args.target].append(rec)
    save_state(state, sf)
    print(json.dumps({"status": "added", "from": args.from_cmd, "target": args.target}))
    return 0


def cmd_clear_recommendations(args: Namespace) -> int:
    state, sf = _load_or_die(args)

    for target_key in state.recommendations:
        state.recommendations[target_key] = [
            r for r in state.recommendations[target_key]
            if not (
                (isinstance(r, dict) and r.get("from") == args.from_cmd)
                or (hasattr(r, "from_cmd") and r.from_cmd == args.from_cmd)
            )
        ]
    save_state(state, sf)
    print(json.dumps({"status": "cleared", "from": args.from_cmd}))
    return 0


def cmd_set_swarm_status(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    pk, ek = str(args.phase), str(args.epic)
    if pk not in state.phases or ek not in state.phases[pk].plans:
        print(f"ERROR: Plan P{args.phase}.E{args.epic} not found", file=sys.stderr)
        return 1
    if args.status_value not in VALID_SWARM_STATUSES:
        print(f"ERROR: Invalid status: {args.status_value}", file=sys.stderr)
        return 1

    sw = state.phases[pk].plans[ek].swarm_execution
    sw.status = args.status_value
    if args.pr_url:
        sw.pr_url = args.pr_url
    if args.pr_number:
        sw.pr_number = args.pr_number
    if args.manifest_path:
        sw.manifest_path = args.manifest_path
    if args.integration_branch:
        sw.integration_branch = args.integration_branch

    save_state(state, sf)
    print(json.dumps({"status": "updated", "swarm_status": args.status_value}))
    return 0


def cmd_add_review_report(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    pk, ek = str(args.phase), str(args.epic)
    sw = state.phases[pk].plans[ek].swarm_execution
    sw.review_reports.append(args.report_path)
    save_state(state, sf)
    print(json.dumps({"status": "added", "report_path": args.report_path}))
    return 0


def cmd_init_plan(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    pk, ek = str(args.phase), str(args.epic)
    if pk not in state.phases:
        print(f"ERROR: Phase {args.phase} not found", file=sys.stderr)
        return 1
    if ek in state.phases[pk].plans:
        print(f"Plan P{args.phase}.E{args.epic} already exists")
        return 0
    state.phases[pk].plans[ek] = EpicPlan()
    save_state(state, sf)
    print(json.dumps({"status": "created", "phase": args.phase, "epic": args.epic}))
    return 0


def cmd_set_phase_review(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    pk = str(args.phase)
    if pk not in state.phases:
        print(f"ERROR: Phase {args.phase} not found", file=sys.stderr)
        return 1
    pr = state.phases[pk].phase_review
    pr.status = args.review_status
    now = _now()
    if args.review_status == "testing":
        pr.summary_presented_at = now
    elif args.review_status == "approved":
        pr.approved_at = now
    if args.testing_recipe:
        pr.testing_recipe = args.testing_recipe
    save_state(state, sf)
    print(json.dumps({"status": "updated", "phase_review": args.review_status}))
    return 0


def cmd_commit_state(args: Namespace) -> int:
    root = _eigen_root()
    sf = _state_file(args)
    additional = args.additional_paths.split(",") if args.additional_paths else None
    ok = git_ops.commit_state(
        message=args.message,
        eigen_root=root,
        state_file=sf,
        additional_paths=additional,
        branch=args.branch or "",
    )
    if ok:
        print(json.dumps({"status": "committed"}))
        return 0
    print("ERROR: git commit/push failed", file=sys.stderr)
    return 1


def cmd_sync(args: Namespace) -> int:
    root = _eigen_root()
    branch = args.branch or _eigen_branch()
    ok = git_ops.sync(branch, root)
    if ok:
        print(json.dumps({"status": "synced", "branch": branch}))
        return 0
    print(f"WARNING: git pull from {branch} failed (may be offline)", file=sys.stderr)
    return 0  # Non-fatal


def cmd_resolve_branch(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    raw = state.to_dict()
    branch = resolve_branch(raw, eigen_branch=_eigen_branch(), eigen_root=_eigen_root())
    if getattr(args, "as_json", False):
        print(json.dumps({"branch": branch}))
    else:
        print(branch)
    return 0


def cmd_checkout_branch(args: Namespace) -> int:
    root = _eigen_root()
    branch = git_ops.integration_branch_name(args.phase, args.epic)
    ok = git_ops.checkout_branch(branch, root, create=args.create)
    if ok:
        print(json.dumps({"status": "checked_out", "branch": branch}))
        return 0
    print(f"ERROR: Failed to checkout {branch}", file=sys.stderr)
    return 1


def cmd_schedule_next(args: Namespace) -> int:
    root = _eigen_root()
    if not root:
        return 0
    sf = resolve_state_file(root)
    state = load_state(sf)
    if state is None:
        return 0

    raw = state.to_dict()
    result = determine_next(raw, eigen_root=root)
    hook_log = resolve_hook_log(root)

    if result is None:
        sched_log_entry(hook_log, {
            "action": "noop", "command": None,
            "context_key": None, "status": "noop",
            "reason": "human checkpoint or complete",
        })
        return 0

    command, context = result
    context_key = make_context_key(context)

    proceed, attempt = check_retry(command, context_key, hook_log)
    if not proceed:
        return 0
    context["_attempt"] = attempt

    api = os.environ.get("CLAUDE_TASKS_API", "")
    if not api:
        print("ERROR: CLAUDE_TASKS_API not set", file=sys.stderr)
        return 1

    success = schedule_command(
        command, context,
        eigen_root=root,
        claude_tasks_api=api,
        hook_log=hook_log,
        delay_minutes=args.delay_minutes,
        telegram_chat_id=os.environ.get("EIGEN_TELEGRAM_CHAT_ID", ""),
        slack_webhook=os.environ.get("EIGEN_SLACK_WEBHOOK", ""),
        discord_webhook=os.environ.get("EIGEN_DISCORD_WEBHOOK", ""),
    )
    return 0 if success else 1


def cmd_validate(args: Namespace) -> int:
    state, sf = _load_or_die(args)
    errors = validate_state(state)
    if not errors:
        print(json.dumps({"valid": True, "errors": []}))
        return 0

    if args.fix:
        save_state(state, sf)
        print(json.dumps({"valid": False, "errors": errors, "fixed": True}))
        return 0

    print(json.dumps({"valid": False, "errors": errors}))
    return 1


def cmd_install(args: Namespace) -> int:
    root = Path(args.root)
    eigen_dir = root / ".eigen"
    eigen_dir.mkdir(parents=True, exist_ok=True)

    # Write env file
    env_lines = [
        f'export EIGEN_ROOT="{root}"',
        f'export EIGEN_BRANCH="{args.branch}"',
        f'export CLAUDE_TASKS_API="{args.tasks_api}"',
    ]
    if args.telegram:
        env_lines.append(f'export EIGEN_TELEGRAM_CHAT_ID="{args.telegram}"')
    if args.slack:
        env_lines.append(f'export EIGEN_SLACK_WEBHOOK="{args.slack}"')
    if args.discord:
        env_lines.append(f'export EIGEN_DISCORD_WEBHOOK="{args.discord}"')
    (eigen_dir / "env").write_text("\n".join(env_lines) + "\n")

    # Write minimal hook script
    hook_content = f"""#!/bin/bash
source "$(dirname "$0")/env" 2>/dev/null || exit 0
python3 -m cli schedule-next 2>/dev/null || true
"""
    hook_path = eigen_dir / "pipeline_hook.sh"
    hook_path.write_text(hook_content)
    hook_path.chmod(0o755)

    # Add .eigen/ to .gitignore
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".eigen/" not in content:
            with open(gitignore, "a") as f:
                f.write("\n.eigen/\n")
    else:
        gitignore.write_text(".eigen/\n")

    print(json.dumps({
        "status": "installed",
        "eigen_dir": str(eigen_dir),
        "hook": str(hook_path),
    }))
    return 0
