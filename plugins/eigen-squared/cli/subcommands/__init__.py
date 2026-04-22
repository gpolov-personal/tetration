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
    MAX_COMMAND_RETRIES,
    MAX_SCHEDULE_FAILURES,
)
from .. import git_ops


# ---------------------------------------------------------------------------
# Exit-code convention (2.5)
# ---------------------------------------------------------------------------
#
# 0  — success; caller proceeds normally
# 1  — generic error; caller retries / surfaces / aborts
# 2  — stalled (max retries reached; operator action required). Used by
#      cmd_schedule_next and observed by the watchdog.
# 3  — idempotent-noop. The requested command has already been completed
#      and re-executing it would be a no-op (e.g. an epic whose PR is
#      already merged, or a swarm whose state is `converged`). Distinct
#      from 1 so the watchdog can advance past the slot instead of
#      retrying it. Returned by the guards in 2.2 / 2.3 / 2.4.
#
# Downstream consumers:
#   - eigen-watchdog.sh treats exit 3 as "not-an-error; advance next
#     tick without warnings".
#   - The LLM invoked by the scheduler sees exit 3 from
#     `eigen-squared get-context` and exits the skill immediately.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_STALLED = 2
EXIT_IDEMPOTENT_NOOP = 3


def _shell_escape(val: str) -> str:
    """Escape a value for safe inclusion in a double-quoted shell string."""
    return val.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")


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


# Maps main commands to their deepen counterparts (commands still using
# the legacy main/deepen pair pattern). bootstrap_converge and
# plan_epic_converge are self-converging and live in CONVERGE_COMMANDS.
MAIN_TO_DEEPEN = {
    "time_split": "deepen_time_split",
}

DEEPEN_TO_MAIN = {v: k for k, v in MAIN_TO_DEEPEN.items()}

# Which commands are "deepen" commands
DEEPEN_COMMANDS = set(DEEPEN_TO_MAIN.keys())

# Which commands are "main" commands (convergence pair left side)
MAIN_COMMANDS = set(MAIN_TO_DEEPEN.keys())

# Self-converging commands (single command, internal swarm convergence loop)
CONVERGE_COMMANDS = {"plan_epic_converge", "bootstrap_converge", "space_split_converge"}


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
        "write-env": cmd_write_env,
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
        bc = phase.bootstrap_converge
        bconv = "converged" if bc.convergence.converged else bc.status
        print(f"  bootstrap_converge   {bconv:12s}  iter {bc.iteration}")
        ssc = phase.space_split_converge
        ssconv = "converged" if ssc.convergence.converged else ssc.status
        print(f"  space_split_converge {ssconv:12s}  iter {ssc.iteration}")

        for ek in sorted(phase.plans.keys(), key=lambda x: int(x)):
            ep = phase.plans[ek]
            pconv = "converged" if ep.plan_epic_converge.convergence.converged else ep.plan_epic_converge.status
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
    root = _eigen_root()

    # 1.3 — auto-sync before reading state.
    # cmd_next is the main entry point for the watchdog, so a stale local
    # view here is what let the 2026-04-22 P2.E1 regression re-launch
    # `create_issues_from_plan_swarm` against a `swarm_execution.status ==
    # not_started` snapshot that had already been superseded on `origin/dev`.
    # Mirrors the auto-sync block in cmd_get_context (225-230): resolve
    # which branch owns the decision, pull it (ff-only via 1.5), then
    # re-load state so determine_next sees the freshest JSON.
    sf = _state_file(args)
    if sf.exists():
        pre_state = load_state(sf)
        if pre_state:
            pre_raw = pre_state.to_dict()
            pre_branch = resolve_branch(
                pre_raw, eigen_branch=_eigen_branch(), eigen_root=root
            )
            if pre_branch and root:
                git_ops.sync(pre_branch, root)

    state, _ = _load_or_die(args)
    raw = state.to_dict()
    result = determine_next(raw, eigen_root=root)

    if result is None:
        if getattr(args, "as_json", False):
            print(json.dumps({"command": None, "context": None}))
        else:
            print("No next command (human checkpoint or pipeline complete)")
        return 0

    cmd, ctx = result
    branch = resolve_branch(raw, eigen_branch=_eigen_branch(), eigen_root=root)
    ctx["branch"] = branch

    if getattr(args, "as_json", False):
        print(json.dumps({"command": cmd, "context": ctx}))
    else:
        print(f"{cmd}")
        for k, v in ctx.items():
            print(f"  {k}: {v}")
    return 0


def cmd_get_context(args: Namespace) -> int:
    root = _eigen_root()

    # Step 1: Auto-sync — pull from the correct branch before reading state.
    # Resolves the branch first (integration branch for swarm commands,
    # EIGEN_BRANCH for everything else), then pulls.
    sf = _state_file(args)
    if sf.exists():
        pre_state = load_state(sf)
        if pre_state:
            raw = pre_state.to_dict()
            branch = resolve_branch(raw, eigen_branch=_eigen_branch(), eigen_root=root)
            if branch and root:
                git_ops.sync(branch, root)

    # Step 2: Reload state after sync (may have changed from pull)
    state, _ = _load_or_die(args)
    cmd = args.target_command
    phase = args.phase
    epic = args.epic

    # Step 3: Auto-detect phase/epic from determine_next if not provided
    if phase is None:
        raw = state.to_dict()
        result = determine_next(raw, eigen_root=root)
        if result and result[0] == cmd:
            ctx = result[1]
            phase = ctx.get("phase")
            epic = epic or ctx.get("epic")
        elif result and result[0] != cmd:
            print(f"ERROR: Next command is {result[0]}, not {cmd}. "
                  f"Run `eigen-squared next` to see what should run.", file=sys.stderr)
            return 1

    if phase is None and cmd not in ("time_split", "deepen_time_split"):
        print(f"ERROR: --phase required for {cmd}", file=sys.stderr)
        return 1

    # Step 4: Resolve branch for this command's context
    branch = _eigen_branch()
    if cmd in ("orchestrate_swarm", "review_swarm_pr", "create_issues_from_plan_swarm"):
        if phase is not None and epic is not None:
            branch = git_ops.integration_branch_name(phase, epic)

    # Base context — only include phase/epic if relevant to this command
    # All paths in context are relative to $EIGEN_ROOT/eigen_initiative/
    context: dict = {"command": cmd, "branch": branch, "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/"}
    if phase is not None:
        context["phase"] = phase
    if epic is not None:
        context["epic"] = epic

    # Build command-specific context
    if cmd in ("time_split", "deepen_time_split"):
        ts = state.time_split
        dts = state.deepen_time_split

        if cmd == "time_split":
            if ts.convergence.converged:
                print(
                    f"ERROR: time_split already converged "
                    f"(iteration {ts.iteration}, decided by "
                    f"{ts.convergence.decided_by} at {ts.convergence.decided_at}). "
                    f"No re-run needed.",
                    file=sys.stderr,
                )
                return 1
            context["iteration"] = ts.iteration + 1
            context["current_iteration"] = ts.iteration
            context["is_first_run"] = ts.iteration == 0
            context["phase_count"] = ts.phase_count

            # Guard: feedback lifecycle checks
            if ts.iteration >= 1:
                # Check if feedback file actually exists on disk
                feedback_exists = False
                if dts.feedback_path and root:
                    feedback_file = Path(root) / "eigen_initiative" / dts.feedback_path
                    feedback_exists = feedback_file.exists()

                if ts.feedback_consumed and not feedback_exists:
                    print(
                        f"ERROR: time_split has already run (iteration {ts.iteration}). "
                        f"Run /deepen_time_split first to generate feedback before re-running.",
                        file=sys.stderr,
                    )
                    return 1
                if ts.feedback_consumed and feedback_exists:
                    print(
                        f"ERROR: Feedback already processed in iteration {ts.iteration}. "
                        f"Run /deepen_time_split again for fresh review before re-running.",
                        file=sys.stderr,
                    )
                    return 1
                if not ts.feedback_consumed and feedback_exists:
                    context["should_process_feedback"] = True
                    context["feedback_path"] = dts.feedback_path
                elif not ts.feedback_consumed and not feedback_exists:
                    print(
                        f"ERROR: time_split iteration {ts.iteration} has unprocessed feedback "
                        f"but feedback file not found at {dts.feedback_path}. "
                        f"Run /deepen_time_split to generate it.",
                        file=sys.stderr,
                    )
                    return 1
            else:
                context["should_process_feedback"] = False

            context["output_paths"] = ts.output_paths
            recs = state.recommendations.get("time_split", [])
            context["recommendations"] = [
                r.to_dict() if hasattr(r, "to_dict") else r for r in recs
            ]
        else:  # deepen_time_split
            if ts.convergence.converged:
                print(
                    f"ERROR: time_split already converged "
                    f"(decided at {ts.convergence.decided_at}: "
                    f"{ts.convergence.reason}). No further review needed.",
                    file=sys.stderr,
                )
                return 1
            if ts.status == "not_started":
                print(
                    "ERROR: time_split has not run yet. "
                    "Run /time_split first to generate the phase split.",
                    file=sys.stderr,
                )
                return 1

            context["iteration"] = dts.iteration + 1
            context["main_command_iteration"] = ts.iteration
            context["phase_count"] = ts.phase_count
            context["lessons_dir"] = "eigen_lessons/time_split/"

            # Enrich main_command_outputs with phase manifests and source files
            outputs = dict(ts.output_paths)
            if ts.phase_count:
                outputs["phase_manifests"] = [
                    f"phases/phase_{i}_manifest.md"
                    for i in range(1, ts.phase_count + 1)
                ]
            # Try to read source_files from initiative_summary
            if root and outputs.get("initiative_summary"):
                summary_path = Path(root) / "eigen_initiative" / outputs["initiative_summary"]
                if summary_path.exists():
                    try:
                        summary = json.loads(summary_path.read_text())
                        if "source_files" in summary:
                            outputs["source_files"] = summary["source_files"]
                    except (json.JSONDecodeError, OSError):
                        pass
            context["main_command_outputs"] = outputs

            # Check if previous feedback exists on disk and warn about overwrite
            if dts.feedback_path and root:
                prev_file = Path(root) / "eigen_initiative" / dts.feedback_path
                context["previous_feedback_path"] = dts.feedback_path
                context["previous_feedback_exists"] = prev_file.exists()
                if prev_file.exists() and not dts.feedback_consumed:
                    context["overwrite_warning"] = (
                        "Existing feedback has not been consumed by time_split yet. "
                        "Re-analyzing will overwrite it."
                    )
            else:
                context["previous_feedback_path"] = None
                context["previous_feedback_exists"] = False

            # Pass locked skills if they exist
            if dts.locked_skills is not None:
                context["locked_skills"] = dts.locked_skills

    elif cmd in ("bootstrap", "deepen_bootstrap", "space_split", "deepen_space_split"):
        # Legacy: redirect to *_converge replacements
        replacement = "bootstrap_converge" if "bootstrap" in cmd else "space_split_converge"
        print(
            f"ERROR: {cmd} has been replaced by {replacement}. "
            f"Use /{replacement} instead.",
            file=sys.stderr,
        )
        return 1

    elif cmd == "bootstrap_converge":
        if phase is None:
            print("ERROR: --phase required for bootstrap_converge", file=sys.stderr)
            return 1
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        bc = state.phases[pk].bootstrap_converge

        if bc.convergence.converged:
            print(
                f"ERROR: bootstrap_converge phase {phase} already converged "
                f"(decided at {bc.convergence.decided_at}: {bc.convergence.reason}). "
                f"No re-run needed.",
                file=sys.stderr,
            )
            return 1

        # Self-converging command: no should_process_feedback flag, no
        # main↔deepen feedback lifecycle. The internal swarm loop manages
        # everything via convergence_state.json.
        # First-run detection uses iteration == 0 (the slot always exists,
        # unlike plan_epic_converge which lazy-inits per-epic).
        context["iteration"] = bc.iteration + 1
        context["current_iteration"] = bc.iteration
        context["is_first_run"] = bc.iteration == 0
        context["output_paths"] = bc.output_paths
        context["phase_manifest"] = f"phases/phase_{phase}_manifest.md"
        context["bootstrap_report"] = f"phases/phase_{phase}/bootstrap-report.json"
        context["lessons_dir"] = "eigen_lessons/bootstrap_converge/"
        # Persisted across crashes — restored to the swarm so the
        # skills-reviewer doesn't re-discover.
        if bc.locked_skills is not None:
            context["locked_skills"] = bc.locked_skills

        recs = [
            r.to_dict() if hasattr(r, "to_dict") else r
            for r in state.recommendations.get("bootstrap_converge", [])
            if (
                (isinstance(r, dict) and r.get("phase") in (phase, None))
                or (hasattr(r, "phase") and r.phase in (phase, None))
            )
        ]
        context["recommendations"] = recs

    elif cmd == "space_split_converge":
        if phase is None:
            print("ERROR: --phase required for space_split_converge", file=sys.stderr)
            return 1
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ssc = state.phases[pk].space_split_converge

        if ssc.convergence.converged:
            print(
                f"ERROR: space_split_converge phase {phase} already converged "
                f"(decided at {ssc.convergence.decided_at}: {ssc.convergence.reason}). "
                f"No re-run needed.",
                file=sys.stderr,
            )
            return 1

        context["iteration"] = ssc.iteration + 1
        context["current_iteration"] = ssc.iteration
        context["is_first_run"] = ssc.iteration == 0
        context["output_paths"] = ssc.output_paths
        context["phase_manifest"] = f"phases/phase_{phase}_manifest.md"
        context["bootstrap_report"] = f"phases/phase_{phase}/bootstrap-report.json"  # input from bootstrap_converge, not an output of this command
        context["lessons_dir"] = "eigen_lessons/space_split_converge/"
        if ssc.locked_skills is not None:
            context["locked_skills"] = ssc.locked_skills

        recs = [
            r.to_dict() if hasattr(r, "to_dict") else r
            for r in state.recommendations.get("space_split_converge", [])
            if (
                (isinstance(r, dict) and r.get("phase") in (phase, None))
                or (hasattr(r, "phase") and r.phase in (phase, None))
            )
        ]
        context["recommendations"] = recs

    elif cmd == "plan_epic_converge":
        if epic is None:
            print("ERROR: --epic required for plan_epic_converge", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ph = state.phases[pk]

        if ek not in ph.plans:
            # First run for this epic — plan entry doesn't exist yet
            context["is_first_run"] = True
            context["iteration"] = 1
            context["current_iteration"] = 0
            context["output_paths"] = {}
            context["phase_manifest"] = f"phases/phase_{phase}_manifest.md"
            context["lessons_dir"] = "eigen_lessons/plan_epic_converge/"
            recs = [
                r.to_dict() if hasattr(r, "to_dict") else r
                for r in state.recommendations.get("plan_epic_converge", [])
                if (
                    (isinstance(r, dict) and r.get("phase") in (phase, None) and r.get("epic") in (epic, None))
                    or (hasattr(r, "phase") and r.phase in (phase, None) and getattr(r, "epic", None) in (epic, None))
                )
            ]
            context["recommendations"] = recs
            if getattr(args, "as_json", False):
                print(json.dumps(context, indent=2))
            else:
                for k, v in context.items():
                    print(f"  {k}: {v}")
            return 0

        pec = ph.plans[ek].plan_epic_converge
        if pec.convergence.converged:
            print(
                f"ERROR: plan_epic_converge P{phase}.E{epic} already converged "
                f"(decided at {pec.convergence.decided_at}: {pec.convergence.reason}). "
                f"No re-run needed.",
                file=sys.stderr,
            )
            return 1

        context["iteration"] = pec.iteration + 1
        context["current_iteration"] = pec.iteration
        context["is_first_run"] = pec.iteration == 0
        context["output_paths"] = pec.output_paths
        context["phase_manifest"] = f"phases/phase_{phase}_manifest.md"
        context["lessons_dir"] = "eigen_lessons/plan_epic_converge/"
        recs = [
            r.to_dict() if hasattr(r, "to_dict") else r
            for r in state.recommendations.get("plan_epic_converge", [])
            if (
                (isinstance(r, dict) and r.get("phase") in (phase, None)
                 and r.get("epic") in (epic, None))
                or (hasattr(r, "phase") and r.phase in (phase, None)
                    and getattr(r, "epic", None) in (epic, None))
            )
        ]
        context["recommendations"] = recs

    elif cmd in ("create_issues_from_plan_swarm", "orchestrate_swarm", "review_swarm_pr"):
        if phase is None or epic is None:
            print(f"ERROR: --phase and --epic required for {cmd}", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        if pk not in state.phases or ek not in state.phases[pk].plans:
            print(f"ERROR: Plan P{phase}.E{epic} not found", file=sys.stderr)
            return 1
        ep = state.phases[pk].plans[ek]
        sw = ep.swarm_execution

        if cmd == "create_issues_from_plan_swarm":
            # Guard: plan must be converged
            if not ep.plan_epic_converge.convergence.converged:
                print(
                    f"ERROR: Plan P{phase}.E{epic} has not converged yet. "
                    f"Run /plan_epic_converge first.",
                    file=sys.stderr,
                )
                return 1
            # Guard: manifest must NOT exist
            if sw.manifest_path is not None:
                print(
                    f"ERROR: Manifest already exists for P{phase}.E{epic} at {sw.manifest_path}. "
                    f"This epic has already been task-ified.",
                    file=sys.stderr,
                )
                return 1
            # 2.2 — Guard C: reject re-run after the PR has already been
            # merged on $EIGEN_BRANCH. This is the fingerprint of the
            # 2026-04-22 P2.E1 regression: pipeline_state.json shows
            # manifest_path == None on stale local state, but the squash
            # of the converged PR already landed on origin/dev. Without
            # this guard, create_issues would happily re-build the
            # manifest and re-launch the swarm against a state that has
            # in fact already completed.
            #
            # Implemented as an advisory guard: if `gh` is unavailable
            # or errors, the guard becomes a no-op (returncode != 0 →
            # skip), preserving today's behavior for environments
            # without gh. Exits with EXIT_IDEMPOTENT_NOOP (3) so the
            # watchdog treats this as "advance, don't retry".
            import subprocess
            branch_name = git_ops.integration_branch_name(phase, epic)
            eigen_branch = _eigen_branch()
            try:
                probe = subprocess.run(
                    [
                        "gh", "pr", "list",
                        "--state", "merged",
                        "--base", eigen_branch,
                        "--head", branch_name,
                        "--json", "number,mergedAt",
                        "--limit", "1",
                    ],
                    cwd=_eigen_root() or None,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                probe = None
            if probe is not None and probe.returncode == 0:
                try:
                    merged = json.loads(probe.stdout or "[]")
                except json.JSONDecodeError:
                    merged = []
                if merged:
                    pr = merged[0]
                    print(
                        f"ERROR: PR #{pr.get('number')} for branch "
                        f"'{branch_name}' is already MERGED (mergedAt="
                        f"{pr.get('mergedAt')}). Pipeline state is "
                        f"stale — run `git -C {_eigen_root()} fetch "
                        f"origin {eigen_branch} && git pull --ff-only "
                        f"origin {eigen_branch}` and retry, or delete "
                        "the integration branch if re-run is truly "
                        "intentional.",
                        file=sys.stderr,
                    )
                    return EXIT_IDEMPOTENT_NOOP
            context["branch"] = git_ops.integration_branch_name(phase, epic)
            context["plan_file"] = ep.plan_epic_converge.output_paths.get("plan_file", f"phases/phase_{phase}/epic_{epic}/plan.md")
            context["epic_file"] = f"phases/phase_{phase}/epic_{epic}/epic.md"
            context["phase_e2e_config"] = f"phases/phase_{phase}/phase_e2e_config.json"
            context["bootstrap_report"] = f"phases/phase_{phase}/bootstrap-report.json"
            context["phase_manifest"] = f"phases/phase_{phase}_manifest.md"
            # Recommendations filtered by phase AND epic
            recs = [
                r.to_dict() if hasattr(r, "to_dict") else r
                for r in state.recommendations.get(cmd, [])
                if (
                    (isinstance(r, dict) and r.get("phase") in (phase, None)
                     and r.get("epic") in (epic, None))
                    or (hasattr(r, "phase") and r.phase in (phase, None)
                        and getattr(r, "epic", None) in (epic, None))
                )
            ]
            context["recommendations"] = recs

        else:  # orchestrate_swarm, review_swarm_pr
            # 2.3 — guard against re-entering orchestrate_swarm after the
            # PR has been created and no fixups are pending. The cron
            # watchdog can schedule orchestrate_swarm twice back-to-back
            # if the state on local dev is stale (the scenario seen on
            # 2026-04-22 P2.E1 when four orchestrate_swarm runs followed
            # the re-run of create_issues). A legitimate fixup re-run
            # shows status == "iterating" (set by review_swarm_pr when
            # it tells orchestrate to go apply fixups), not
            # status == "pr_created".
            if cmd == "orchestrate_swarm" and sw.status == "pr_created":
                print(
                    f"ERROR: orchestrate_swarm P{phase}.E{epic} refused: "
                    f"swarm_execution.status is 'pr_created' (PR "
                    f"#{sw.pr_number}). Either the pipeline already "
                    "created the PR and is awaiting review, or the "
                    "local state is stale. If you intend a fixup re-run, "
                    "review_swarm_pr must set status to 'iterating' "
                    "first.",
                    file=sys.stderr,
                )
                return EXIT_IDEMPOTENT_NOOP

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
        state.time_split.status = "iterating"  # signal main command needs re-run
        if args.feedback_path:
            dts.feedback_path = args.feedback_path
        if args.findings_summary:
            from ..models import FindingsSummary
            fs = json.loads(args.findings_summary)
            dts.findings_summary = FindingsSummary.from_dict(fs)
        if args.locked_skills:
            dts.locked_skills = json.loads(args.locked_skills)

    elif cmd in ("bootstrap", "deepen_bootstrap", "space_split", "deepen_space_split"):
        # Legacy: redirect to *_converge replacements
        replacement = "bootstrap_converge" if "bootstrap" in cmd else "space_split_converge"
        print(
            f"ERROR: {cmd} has been replaced by {replacement}. "
            f"Use /{replacement} instead.",
            file=sys.stderr,
        )
        return 1

    elif cmd == "space_split_converge":
        if phase is None:
            print("ERROR: --phase required for space_split_converge", file=sys.stderr)
            return 1
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        ssc = state.phases[pk].space_split_converge
        ssc.status = "completed"
        ssc.iteration += 1
        ssc.last_run_at = now
        # Self-converging: feedback_consumed is NOT toggled by the CLI.
        # The internal swarm loop manages all feedback state.
        if args.epic_manifest:
            ssc.output_paths["epic_manifest"] = args.epic_manifest
        if args.e2e_config:
            ssc.output_paths["phase_e2e_config"] = args.e2e_config
        if args.epic_ids:
            ssc.output_paths["epic_ids"] = json.loads(args.epic_ids)
        if args.output_path:
            ssc.output_paths["space_split_report"] = args.output_path
        if args.feedback_path:
            ssc.output_paths["feedback_file"] = args.feedback_path
        if args.findings_summary:
            from ..models import FindingsSummary
            fs = json.loads(args.findings_summary)
            ssc.findings_summary = FindingsSummary.from_dict(fs)
        if args.locked_skills:
            ssc.locked_skills = json.loads(args.locked_skills)

    elif cmd == "bootstrap_converge":
        if phase is None:
            print("ERROR: --phase required for bootstrap_converge", file=sys.stderr)
            return 1
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        bc = state.phases[pk].bootstrap_converge
        bc.status = "completed"
        bc.iteration += 1
        bc.last_run_at = now
        # NOTE: feedback_consumed is NOT toggled by the CLI for self-converging
        # commands. The internal swarm loop manages all feedback state.
        if args.output_path:
            bc.output_paths["bootstrap_report"] = args.output_path
            bc.output_paths["target_repo"] = _eigen_root()
        if args.feedback_path:
            bc.output_paths["feedback_file"] = args.feedback_path
        if args.findings_summary:
            from ..models import FindingsSummary
            fs = json.loads(args.findings_summary)
            bc.findings_summary = FindingsSummary.from_dict(fs)
        if args.locked_skills:
            bc.locked_skills = json.loads(args.locked_skills)

    elif cmd == "plan_epic_converge":
        if phase is None or epic is None:
            print("ERROR: --phase and --epic required", file=sys.stderr)
            return 1
        pk, ek = str(phase), str(epic)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return 1
        if ek not in state.phases[pk].plans:
            state.phases[pk].plans[ek] = EpicPlan()
        pec = state.phases[pk].plans[ek].plan_epic_converge
        pec.status = "completed"
        pec.iteration += 1
        pec.last_run_at = now
        if args.plan_file:
            pec.output_paths["plan_file"] = args.plan_file
        if args.feedback_path:
            pec.output_paths["feedback_file"] = args.feedback_path
        if args.findings_summary:
            from ..models import FindingsSummary
            fs = json.loads(args.findings_summary)
            pec.findings_summary = FindingsSummary.from_dict(fs)

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
        # Status stays as-is here (pr_created). The command decides:
        # - If findings remain: set-swarm-status iterating (creates fixup tasks)
        # - If zero findings: mark-converged swarm_execution (sets converged)
        # Do NOT hardcode status — the command controls the decision.
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
        # Legacy: redirect to bootstrap_converge
        print(
            "ERROR: bootstrap has been replaced by bootstrap_converge. "
            "Use `eigen-squared mark-converged bootstrap_converge --phase N` instead.",
            file=sys.stderr,
        )
        return 1
    elif cmd == "bootstrap_converge" and phase is not None:
        caller = "bootstrap_converge"  # self-marking, like plan_epic_converge
        target = state.phases[str(phase)].bootstrap_converge
    elif cmd in ("space_split", "deepen_space_split") and phase is not None:
        # Legacy: redirect to space_split_converge
        print(
            f"ERROR: {cmd} has been replaced by space_split_converge. "
            "Use `eigen-squared mark-converged space_split_converge --phase N` instead.",
            file=sys.stderr,
        )
        return 1
    elif cmd == "space_split_converge" and phase is not None:
        caller = "space_split_converge"  # self-marking, like bootstrap_converge
        target = state.phases[str(phase)].space_split_converge
    elif cmd == "plan_epic_converge" and phase is not None and epic is not None:
        caller = "plan_epic_converge"
        target = state.phases[str(phase)].plans[str(epic)].plan_epic_converge
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
    # 1.5 — a failed ff-only pull means the local branch is either behind
    # the remote in a way that cannot fast-forward (diverged history,
    # force-push upstream) or unreachable. Either way, decisions made
    # against the stale local state are unsafe — surface it with a real
    # non-zero exit so the watchdog / invoking LLM treats it as an error
    # instead of continuing on a silent warning.
    print(
        f"ERROR: git pull --ff-only origin {branch} failed "
        "(diverged history, network, or auth). Local state may be stale.",
        file=sys.stderr,
    )
    return 1


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
    ok = git_ops.checkout_branch(
        branch, root,
        create=args.create,
        base_branch=_eigen_branch() if args.create else "",
    )
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
        if attempt > MAX_COMMAND_RETRIES:
            print(
                json.dumps({"status": "stalled", "command": command,
                            "context_key": context_key, "attempt": attempt}),
                file=sys.stderr,
            )
            return 2  # Distinct exit code: stalled
        return 0  # Dedup — not an error
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
        extra_prompt=getattr(args, "extra_prompt", ""),
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


def cmd_write_env(args: Namespace) -> int:
    """Regenerate .eigen/env from .claude/settings.json."""
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return 1

    settings_path = Path(root) / ".claude" / "settings.json"
    if not settings_path.exists():
        print(f"ERROR: {settings_path} not found", file=sys.stderr)
        return 1

    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Failed to read settings: {e}", file=sys.stderr)
        return 1

    env_vars = settings.get("env", {})

    # Build env lines from settings.json env block (same format as cmd_install)
    env_lines = []
    for key, val in env_vars.items():
        env_lines.append(f'export {key}="{_shell_escape(str(val))}"')

    env_path = Path(root) / ".eigen" / "env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(env_lines) + "\n")
    os.chmod(str(env_path), 0o600)

    print(json.dumps({"status": "written", "path": str(env_path), "keys": list(env_vars.keys())}))
    return 0


def cmd_install(args: Namespace) -> int:
    root = Path(args.root)
    eigen_dir = root / ".eigen"
    eigen_dir.mkdir(parents=True, exist_ok=True)

    # Write env file
    env_lines = [
        f'export EIGEN_ROOT="{_shell_escape(str(root))}"',
        f'export EIGEN_BRANCH="{_shell_escape(args.branch)}"',
        f'export CLAUDE_TASKS_API="{_shell_escape(args.tasks_api)}"',
    ]
    if args.telegram:
        env_lines.append(f'export EIGEN_TELEGRAM_CHAT_ID="{_shell_escape(args.telegram)}"')
    if args.slack:
        env_lines.append(f'export EIGEN_SLACK_WEBHOOK="{_shell_escape(args.slack)}"')
    if args.discord:
        env_lines.append(f'export EIGEN_DISCORD_WEBHOOK="{_shell_escape(args.discord)}"')
    env_file = eigen_dir / "env"
    env_file.write_text("\n".join(env_lines) + "\n")
    os.chmod(str(env_file), 0o600)

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
    }))
    return 0
