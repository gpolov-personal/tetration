"""Subcommand dispatch."""

from __future__ import annotations

import json
import os
import subprocess
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
    THREAT_CLASS_ENUM,
    VALID_SWARM_STATUSES,
)
from ..state import (
    create_initial_state,
    load_state,
    locked_state,
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


def _gh_probe_json(
    gh_args: list[str], cwd: str = "", timeout: int = 15
):
    """S18 — advisory-mode ``gh`` probe that returns parsed JSON.

    Returns the parsed JSON payload on success, or ``None`` when the
    probe could not complete (``gh`` missing, timed out, non-zero exit,
    invalid JSON, OS-level error). The three 2.2 / 2.4 / 2.7 guards
    previously inlined this same shape; consolidating removes ~60 LoC
    of near-duplicated subprocess plumbing and makes the advisory
    semantics (``None`` ≠ failure) a single, greppable contract.

    Callers must decide what ``None`` means locally. For the phase-
    approval check we keep the existing "gh unreachable → don't block"
    policy; for the swarm-entry guards the same policy preserves local
    offline testing.
    """
    try:
        probe = subprocess.run(
            ["gh"] + gh_args,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if probe.returncode != 0:
        return None
    try:
        return json.loads(probe.stdout or "null")
    except json.JSONDecodeError:
        return None


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
        sys.exit(EXIT_ERROR)
    return resolve_state_file(root)


def _load_or_die(args: Namespace) -> tuple[PipelineState, Path]:
    sf = _state_file(args)
    state = load_state(sf)
    if state is None:
        print(f"ERROR: Cannot load {sf}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
    return state, sf


def _with_state_lock(handler):
    """B1 — decorator that acquires the pipeline_state.json flock for the
    full duration of a mutating handler.

    Applied at dispatch time (see ``dispatch`` below) so the handler
    bodies stay unchanged. The lock serializes concurrent
    ``load_state → mutate → save_state`` cycles — 1.1's atomic rename
    prevents torn *reads* but not lost *updates* when two writers race
    (e.g. watchdog-spawned LLM task + a manual
    ``eigen-squared add-recommendation``). The held region covers the
    entire handler, so a ``sys.exit`` inside ``_load_or_die`` still
    releases the lock via ``locked_state``'s ``finally``.
    """

    def wrapped(args: Namespace) -> int:
        sf = _state_file(args)
        with locked_state(sf):
            return handler(args)

    wrapped.__name__ = handler.__name__
    return wrapped


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# The legacy main/deepen pair pattern is no longer used by any command —
# time_split was the last pair and is now self-converging (single session).
# These maps are kept (empty) for backward-compatible imports.
MAIN_TO_DEEPEN: dict[str, str] = {}

DEEPEN_TO_MAIN = {v: k for k, v in MAIN_TO_DEEPEN.items()}

# Which commands are "deepen" commands
DEEPEN_COMMANDS = set(DEEPEN_TO_MAIN.keys())

# Which commands are "main" commands (convergence pair left side)
MAIN_COMMANDS = set(MAIN_TO_DEEPEN.keys())

# Self-converging commands (single command, internal self-critique convergence loop)
CONVERGE_COMMANDS = {"time_split", "plan_epic_converge", "bootstrap_converge", "space_split_converge"}


def dispatch(args: Namespace) -> int:
    """Route to the appropriate subcommand handler.

    Commands that mutate ``pipeline_state.json`` (load→save cycles)
    are wrapped with ``_with_state_lock`` so concurrent invocations
    cannot produce lost updates.
    """
    handlers = {
        "init": _with_state_lock(cmd_init),
        "status": cmd_status,
        "next": cmd_next,
        "get-context": cmd_get_context,
        "complete": _with_state_lock(cmd_complete),
        "mark-converged": _with_state_lock(cmd_mark_converged),
        "add-recommendation": _with_state_lock(cmd_add_recommendation),
        "clear-recommendations": _with_state_lock(cmd_clear_recommendations),
        "set-swarm-status": _with_state_lock(cmd_set_swarm_status),
        "finalize-iteration": _with_state_lock(cmd_finalize_iteration),
        "add-review-report": _with_state_lock(cmd_add_review_report),
        "init-plan": _with_state_lock(cmd_init_plan),
        "set-phase-review": _with_state_lock(cmd_set_phase_review),
        "commit-state": _with_state_lock(cmd_commit_state),
        "sync": cmd_sync,
        "resolve-branch": cmd_resolve_branch,
        "checkout-branch": cmd_checkout_branch,
        "schedule-next": cmd_schedule_next,
        "validate": _with_state_lock(cmd_validate),
        "install": cmd_install,
        "write-env": cmd_write_env,
    }
    handler = handlers.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return EXIT_ERROR
    return handler(args)


# ─────────────────────────────────────────────────────────────────────────────
# SUBCOMMAND IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────────────────────


def cmd_init(args: Namespace) -> int:
    sf = _state_file(args)
    if sf.exists():
        print(f"ERROR: {sf} already exists. Delete it first to re-initialize.", file=sys.stderr)
        return EXIT_ERROR
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
    conv = "converged" if ts.convergence.converged else ts.status
    print(f"  time_split          {conv:12s}  iter {ts.iteration}")
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


def _sync_and_reload(
    root: str, sf: Path, caller: str,
) -> int | None:
    """S2 + N6 — TOCTOU-safe two-phase sync shared by cmd_next and
    cmd_get_context.

    1. Sync $EIGEN_BRANCH (canonical source of truth for
       pipeline_state.json).
    2. Reload state, re-resolve the decision branch — if it points at
       an integration branch (swarm commands), sync that too.

    Returns ``None`` on success (caller should proceed), or an int
    exit code if the sync failed (caller should return it).

    Skips silently when there is no ``.git`` directory (tests, local
    scaffolds without a remote).
    """
    has_git = bool(root) and (Path(root) / ".git").exists()
    if not has_git or not sf.exists():
        return None

    eigen_branch = _eigen_branch()
    if not git_ops.sync(eigen_branch, root):
        print(
            f"ERROR: git pull --ff-only origin {eigen_branch} failed "
            "(diverged history, network, or auth). Local state may "
            f"be stale; refusing to proceed ({caller}).",
            file=sys.stderr,
        )
        return EXIT_ERROR

    post_state = load_state(sf)
    if post_state:
        post_raw = post_state.to_dict()
        resolved = resolve_branch(
            post_raw, eigen_branch=eigen_branch, eigen_root=root
        )
        if resolved and resolved != eigen_branch:
            if not git_ops.sync(resolved, root):
                print(
                    f"ERROR: git pull --ff-only origin {resolved} "
                    "failed. Local integration-branch state may be "
                    f"stale; refusing to proceed ({caller}).",
                    file=sys.stderr,
                )
                return EXIT_ERROR
    return None


def cmd_next(args: Namespace) -> int:
    root = _eigen_root()
    sf = _state_file(args)

    err = _sync_and_reload(root, sf, caller="cmd_next")
    if err is not None:
        return err

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
    sf = _state_file(args)

    # N6 — apply the same S2 TOCTOU-safe two-phase sync as cmd_next.
    # The previous one-shot form resolved branch from pre-sync state
    # and ignored the sync return value.
    err = _sync_and_reload(root, sf, caller="cmd_get_context")
    if err is not None:
        return err

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
            return EXIT_ERROR

    if phase is None and cmd != "time_split":
        print(f"ERROR: --phase required for {cmd}", file=sys.stderr)
        return EXIT_ERROR

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
    if cmd == "time_split":
        ts = state.time_split
        if ts.convergence.converged:
            print(
                f"ERROR: time_split already converged "
                f"(iteration {ts.iteration}, decided by "
                f"{ts.convergence.decided_by} at {ts.convergence.decided_at}). "
                f"No re-run needed.",
                file=sys.stderr,
            )
            return EXIT_ERROR
        # Self-converging command: a single session drafts the phase split,
        # self-critiques against the review checklists, and revises. No
        # main↔deepen feedback lifecycle / should_process_feedback flag.
        # First-run detection uses iteration == 0 (the slot always exists).
        context["iteration"] = ts.iteration + 1
        context["current_iteration"] = ts.iteration
        context["is_first_run"] = ts.iteration == 0
        context["phase_count"] = ts.phase_count
        context["output_paths"] = ts.output_paths
        context["lessons_dir"] = "eigen_lessons/time_split/"
        if ts.locked_skills is not None:
            context["locked_skills"] = ts.locked_skills
        recs = state.recommendations.get("time_split", [])
        context["recommendations"] = [
            r.to_dict() if hasattr(r, "to_dict") else r for r in recs
        ]

    elif cmd in ("bootstrap", "deepen_bootstrap", "space_split", "deepen_space_split"):
        # Legacy: redirect to *_converge replacements
        replacement = "bootstrap_converge" if "bootstrap" in cmd else "space_split_converge"
        print(
            f"ERROR: {cmd} has been replaced by {replacement}. "
            f"Use /{replacement} instead.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    elif cmd == "bootstrap_converge":
        if phase is None:
            print("ERROR: --phase required for bootstrap_converge", file=sys.stderr)
            return EXIT_ERROR
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
        bc = state.phases[pk].bootstrap_converge

        if bc.convergence.converged:
            print(
                f"ERROR: bootstrap_converge phase {phase} already converged "
                f"(decided at {bc.convergence.decided_at}: {bc.convergence.reason}). "
                f"No re-run needed.",
                file=sys.stderr,
            )
            return EXIT_ERROR

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
            return EXIT_ERROR
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
        ssc = state.phases[pk].space_split_converge

        if ssc.convergence.converged:
            print(
                f"ERROR: space_split_converge phase {phase} already converged "
                f"(decided at {ssc.convergence.decided_at}: {ssc.convergence.reason}). "
                f"No re-run needed.",
                file=sys.stderr,
            )
            return EXIT_ERROR

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
            return EXIT_ERROR
        pk, ek = str(phase), str(epic)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
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
            return EXIT_ERROR

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
            return EXIT_ERROR
        pk, ek = str(phase), str(epic)
        if pk not in state.phases or ek not in state.phases[pk].plans:
            print(f"ERROR: Plan P{phase}.E{epic} not found", file=sys.stderr)
            return EXIT_ERROR
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
                return EXIT_ERROR
            # Guard: manifest must NOT exist
            if sw.manifest_path is not None:
                print(
                    f"ERROR: Manifest already exists for P{phase}.E{epic} at {sw.manifest_path}. "
                    f"This epic has already been task-ified.",
                    file=sys.stderr,
                )
                return EXIT_ERROR
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
            branch_name = git_ops.integration_branch_name(phase, epic)
            eigen_branch = _eigen_branch()
            merged = _gh_probe_json(
                [
                    "pr", "list",
                    "--state", "merged",
                    "--base", eigen_branch,
                    "--head", branch_name,
                    "--json", "number,mergedAt",
                    "--limit", "1",
                ],
                cwd=_eigen_root() or "",
            )
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

            # 2.4 — guard review_swarm_pr against re-entry after convergence
            # and against chasing an already-merged or closed PR.
            if cmd == "review_swarm_pr":
                if sw.convergence.converged:
                    print(
                        f"ERROR: review_swarm_pr P{phase}.E{epic} refused: "
                        f"swarm_execution.convergence.converged is True. "
                        f"The review loop has already completed. If "
                        "you need to re-review, reset the convergence "
                        "flag and start a new iteration manually.",
                        file=sys.stderr,
                    )
                    return EXIT_IDEMPOTENT_NOOP
                # PR-state probe via gh. Advisory — if gh is missing,
                # errors, or times out, we fall through to normal entry.
                if sw.pr_number:
                    pr_data = _gh_probe_json(
                        ["pr", "view", str(sw.pr_number), "--json", "state"],
                        cwd=_eigen_root() or "",
                    )
                    if isinstance(pr_data, dict):
                        pr_state = pr_data.get("state")
                        if pr_state in ("MERGED", "CLOSED"):
                            print(
                                f"ERROR: review_swarm_pr P{phase}.E{epic} "
                                f"refused: PR #{sw.pr_number} is "
                                f"{pr_state}. Pipeline state still "
                                f"reports swarm_execution.status="
                                f"'{sw.status}' — local JSON is stale. "
                                f"Run `git -C {_eigen_root()} fetch "
                                f"origin {_eigen_branch()} && git pull "
                                f"--ff-only origin {_eigen_branch()}` "
                                "to reconcile.",
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
        if args.findings_summary:
            from ..models import FindingsSummary
            ts.findings_summary = FindingsSummary.from_dict(json.loads(args.findings_summary))
        if args.locked_skills:
            ts.locked_skills = json.loads(args.locked_skills)

    elif cmd in ("bootstrap", "deepen_bootstrap", "space_split", "deepen_space_split"):
        # Legacy: redirect to *_converge replacements
        replacement = "bootstrap_converge" if "bootstrap" in cmd else "space_split_converge"
        print(
            f"ERROR: {cmd} has been replaced by {replacement}. "
            f"Use /{replacement} instead.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    elif cmd == "space_split_converge":
        if phase is None:
            print("ERROR: --phase required for space_split_converge", file=sys.stderr)
            return EXIT_ERROR
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
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
            return EXIT_ERROR
        pk = str(phase)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
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
            return EXIT_ERROR
        pk, ek = str(phase), str(epic)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
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
            return EXIT_ERROR
        pk, ek = str(phase), str(epic)
        if pk not in state.phases:
            print(f"ERROR: Phase {phase} not found", file=sys.stderr)
            return EXIT_ERROR
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
            return EXIT_ERROR
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
            return EXIT_ERROR
        pk, ek = str(phase), str(epic)
        sw = state.phases[pk].plans[ek].swarm_execution
        # 2.6 — refuse to bump review_iteration when the review has
        # already converged. Without this guard a stray re-invocation
        # of `complete review_swarm_pr` (e.g. from a retry loop or a
        # cross-branch race) would keep incrementing the counter past
        # the iteration_limit, desynchronize it from the on-disk
        # review_report_iteration_N.md filenames, and confuse the
        # convergence-with-residual-P3 accounting.
        if sw.convergence.converged:
            print(
                f"ERROR: cannot complete review_swarm_pr for P{phase}.E{epic}: "
                "swarm_execution.convergence.converged is already True. "
                "The review loop is complete; further iterations are "
                "not counted.",
                file=sys.stderr,
            )
            return EXIT_IDEMPOTENT_NOOP
        sw.review_iteration += 1
        # Status stays as-is here (pr_created). The command decides:
        # - If findings remain: set-swarm-status iterating (creates fixup tasks)
        # - If zero findings: mark-converged swarm_execution (sets converged)
        # Do NOT hardcode status — the command controls the decision.
        if args.report_path:
            sw.review_reports.append(args.report_path)
        if args.findings_summary:
            sw.findings_summary = json.loads(args.findings_summary)
        # S-T1-4: append per-iteration detail (counts + signatures + entries) to
        # findings_history. Consumed by review_swarm_pr's oscillation rule
        # (same (file, category) appearing in >=3 distinct iterations
        # triggers CAPPED_BY_OSCILLATION), Step 5's prior-context threading,
        # and compound_improve's cross-epic aggregator.
        detail_err = _ingest_findings_detail(args.findings_detail, sw)
        if detail_err is not None:
            return detail_err

    else:
        print(f"ERROR: Unknown command or missing --phase: {cmd}", file=sys.stderr)
        return EXIT_ERROR

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
        caller = "time_split"  # self-marking, like the other converge commands
        target = state.time_split
    elif cmd == "bootstrap" and phase is not None:
        # Legacy: redirect to bootstrap_converge
        print(
            "ERROR: bootstrap has been replaced by bootstrap_converge. "
            "Use `eigen-squared mark-converged bootstrap_converge --phase N` instead.",
            file=sys.stderr,
        )
        return EXIT_ERROR
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
        return EXIT_ERROR
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
        return EXIT_ERROR

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
        return EXIT_ERROR
    if args.target not in allowed_targets:
        print(f"ERROR: {args.from_cmd} cannot recommend to {args.target}", file=sys.stderr)
        return EXIT_ERROR

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
        return EXIT_ERROR

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
        return EXIT_ERROR
    if args.status_value not in VALID_SWARM_STATUSES:
        print(f"ERROR: Invalid status: {args.status_value}", file=sys.stderr)
        return EXIT_ERROR

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


def _ingest_findings_detail(detail_arg: str | None, sw) -> int | None:
    """Process --findings-detail file and append to ``sw.findings_history``.

    Returns ``None`` on success (or when ``detail_arg`` is None), or an
    ``EXIT_*`` code on validation failure. Mutates ``sw.findings_history``
    in place.

    Shared between ``cmd_complete`` (review_swarm_pr branch) and
    ``cmd_finalize_iteration`` so the validation rules stay identical
    across both code paths.
    """
    if not detail_arg:
        return None
    try:
        detail_path = Path(detail_arg)
        detail = json.loads(detail_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: --findings-detail {detail_arg}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        detail_iter = int(detail.get("iteration"))
    except (TypeError, ValueError):
        print("ERROR: --findings-detail JSON missing/invalid 'iteration'", file=sys.stderr)
        return EXIT_ERROR
    if detail_iter != sw.review_iteration - 1:
        print(
            f"ERROR: --findings-detail iteration {detail_iter} does not match "
            f"the iteration just completed ({sw.review_iteration - 1}). "
            "Refusing to corrupt findings_history.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    sigs = detail.get("signatures") or []
    if not isinstance(sigs, list) or not all(isinstance(s, str) for s in sigs):
        print("ERROR: --findings-detail 'signatures' must be a list of strings", file=sys.stderr)
        return EXIT_ERROR
    entries_raw = detail.get("entries") or []
    if not isinstance(entries_raw, list):
        print("ERROR: --findings-detail 'entries' must be a list", file=sys.stderr)
        return EXIT_ERROR
    entries_validated: list = []
    for idx, e in enumerate(entries_raw):
        if not isinstance(e, dict):
            print(f"ERROR: --findings-detail 'entries[{idx}]' must be an object", file=sys.stderr)
            return EXIT_ERROR
        for required_key in ("signature", "severity", "file", "category", "threat_class"):
            if required_key not in e:
                print(
                    f"ERROR: --findings-detail 'entries[{idx}]' missing required '{required_key}'",
                    file=sys.stderr,
                )
                return EXIT_ERROR
        if e["severity"] not in ("P1", "P2", "P3"):
            print(
                f"ERROR: --findings-detail 'entries[{idx}].severity' must be P1|P2|P3",
                file=sys.stderr,
            )
            return EXIT_ERROR
        if e["threat_class"] not in THREAT_CLASS_ENUM:
            print(
                f"ERROR: --findings-detail 'entries[{idx}].threat_class'={e['threat_class']!r} "
                f"not in closed enum. Allowed: {sorted(THREAT_CLASS_ENUM)}",
                file=sys.stderr,
            )
            return EXIT_ERROR
        entries_validated.append({
            "signature": e["signature"],
            "severity": e["severity"],
            "file": e["file"],
            "category": e["category"],
            "threat_class": e["threat_class"],
            "title_normalized": e.get("title_normalized", ""),
        })
    entry = {
        "iteration": detail_iter,
        "p1": int(detail.get("p1", 0)),
        "p2": int(detail.get("p2", 0)),
        "p3": int(detail.get("p3", 0)),
        "signatures": sigs,
        "signature_version": 2,
        "entries": entries_validated,
    }
    existing = next(
        (i for i, e in enumerate(sw.findings_history)
         if isinstance(e, dict) and e.get("iteration") == detail_iter),
        None,
    )
    if existing is not None:
        sw.findings_history[existing] = entry
    else:
        sw.findings_history.append(entry)
    return None


def cmd_finalize_iteration(args: Namespace) -> int:
    """Atomic merge of `complete review_swarm_pr` + status update.

    Performs the same on-disk mutations as the legacy two-call sequence
    (``complete review_swarm_pr`` followed by either ``mark-converged
    swarm_execution`` or ``set-swarm-status iterating``) but inside a
    single state-lock + single ``save_state`` call. A SIGKILL between
    the two legacy calls used to leave partial state on disk; this verb
    eliminates that window.

    The on-disk effect is byte-equivalent to the legacy sequence — the
    legacy verbs remain available for non-hot-path callers.
    """
    state, sf = _load_or_die(args)
    phase, epic = args.phase, args.epic
    pk, ek = str(phase), str(epic)
    if pk not in state.phases or ek not in state.phases[pk].plans:
        print(f"ERROR: Plan P{phase}.E{epic} not found", file=sys.stderr)
        return EXIT_ERROR

    if args.status == "converged" and not args.reason:
        print("ERROR: --reason required when --status converged", file=sys.stderr)
        return EXIT_ERROR

    sw = state.phases[pk].plans[ek].swarm_execution
    now = _now()

    # === complete review_swarm_pr (mirrors cmd_complete review_swarm_pr branch) ===
    if sw.convergence.converged:
        print(
            f"ERROR: cannot finalize review_swarm_pr for P{phase}.E{epic}: "
            "swarm_execution.convergence.converged is already True. "
            "The review loop is complete; further iterations are not counted.",
            file=sys.stderr,
        )
        return EXIT_IDEMPOTENT_NOOP
    sw.review_iteration += 1
    if args.report_path:
        sw.review_reports.append(args.report_path)
    if args.findings_summary:
        sw.findings_summary = json.loads(args.findings_summary)
    detail_err = _ingest_findings_detail(args.findings_detail, sw)
    if detail_err is not None:
        return detail_err

    # === apply status (mirrors cmd_mark_converged swarm_execution branch
    #     or cmd_set_swarm_status iterating branch) ===
    if args.status == "converged":
        sw.convergence.converged = True
        sw.convergence.decided_by = "review_swarm_pr"
        sw.convergence.decided_at = now
        sw.convergence.reason = args.reason
        sw.status = "converged"
    else:  # "iterating"
        sw.status = "iterating"

    # Parity with set-swarm-status: callers that need to attach PR
    # metadata atomically with the status flip pass these flags. Empty
    # values are skipped so the verb stays compatible with callers that
    # don't need them (typical Case 1.1 path).
    if getattr(args, "pr_url", None):
        sw.pr_url = args.pr_url
    if getattr(args, "pr_number", None):
        sw.pr_number = args.pr_number
    if getattr(args, "manifest_path", None):
        sw.manifest_path = args.manifest_path
    if getattr(args, "integration_branch", None):
        sw.integration_branch = args.integration_branch

    save_state(state, sf)
    print(json.dumps({
        "status": "finalized",
        "swarm_status": sw.status,
        "iteration": sw.review_iteration - 1,
        "converged": sw.convergence.converged,
    }))
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
        return EXIT_ERROR
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
        return EXIT_ERROR
    pr = state.phases[pk].phase_review

    # 2.7 — before approving a phase, verify every epic swarm has a
    # merged PR on $EIGEN_BRANCH. The old behavior accepted
    # --review-status approved purely on the operator's word, with no
    # cross-check against GitHub. That let a human respond "Yes" in
    # eigen_continue Mode 2 even when the PRs were still open — the
    # pipeline would advance to phase N+1 on an inconsistent base.
    #
    # The check runs only for status=approved and degrades gracefully
    # when `gh` is absent (no-op). Can be bypassed by passing
    # --force-approve for operator discretion (e.g. manual merges done
    # via CLI, not via PR).
    if args.review_status == "approved" and not getattr(args, "force_approve", False):
        phase = state.phases[pk]

        # S6 — an epic with status ∈ {pr_created, iterating, converged}
        # but no recorded pr_number is a state/GitHub desync: the
        # orchestrate/review loop got far enough to set a non-terminal
        # status but the pr_number was never persisted (likely
        # orchestrate_swarm crashed between creating the PR and
        # committing state, or a pre-pr_number release wrote the state).
        # The prior code silently `continue`-d past such epics; with
        # them excluded, ``probed_any`` could end up False and the
        # approval passed. Treat them as a blocker regardless of the
        # gh probe outcome.
        desynced: list[str] = []
        for ek, ep in phase.plans.items():
            sw = ep.swarm_execution
            if not sw.pr_number and sw.status in (
                "pr_created", "iterating", "converged",
            ):
                desynced.append(ek)
        if desynced:
            details = ", ".join(f"P{args.phase}.E{ek}" for ek in desynced)
            print(
                f"ERROR: cannot approve phase {args.phase}: the "
                f"following epic(s) have swarm_execution.status in "
                f"{{pr_created, iterating, converged}} but no recorded "
                f"pr_number: {details}. This indicates a state/GitHub "
                "desync — the PR may exist on origin without having "
                "been recorded, or the local state is stale. "
                "Reconcile before approving (pull latest, or pass "
                "--force-approve if the merges were performed "
                "out-of-band).",
                file=sys.stderr,
            )
            return EXIT_ERROR

        # S11 — single batched `gh pr list` instead of N sequential
        # `gh pr view`s. At N=20 epics this is ~15s vs. ~400-800ms.
        # `--state all` covers OPEN/MERGED/CLOSED so we can classify
        # each recorded pr_number without another round-trip.
        eigen_branch = _eigen_branch()
        all_prs = _gh_probe_json(
            [
                "pr", "list",
                "--base", eigen_branch,
                "--state", "all",
                "--json", "number,state",
                "--limit", "200",
            ],
            cwd=_eigen_root() or "",
        )
        unmerged: list[tuple[str, int]] = []
        probed_any = isinstance(all_prs, list)
        if probed_any:
            states_by_number = {
                p.get("number"): p.get("state")
                for p in all_prs  # type: ignore[union-attr]
                if isinstance(p, dict)
            }
            for ek, ep in phase.plans.items():
                sw = ep.swarm_execution
                if not sw.pr_number:
                    continue
                # Absence from the batched result is treated as unmerged
                # (pessimistic): either the PR has a different --base,
                # was deleted, or fell outside the --limit. Any of those
                # warrants a stop-and-reconcile.
                if states_by_number.get(sw.pr_number) != "MERGED":
                    unmerged.append((ek, sw.pr_number))
        if probed_any and unmerged:
            details = ", ".join(
                f"P{args.phase}.E{ek} (PR #{n})" for ek, n in unmerged
            )
            print(
                f"ERROR: cannot approve phase {args.phase}: the "
                f"following epic PR(s) are not MERGED: {details}. "
                "Either merge them via `gh pr merge` (or GitHub UI) "
                "and re-run, or pass --force-approve if the merges "
                "were performed out-of-band.",
                file=sys.stderr,
            )
            return EXIT_ERROR

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
    return EXIT_ERROR


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
    return EXIT_ERROR


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
    return EXIT_ERROR


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
            return EXIT_STALLED
        return 0  # Dedup — not an error
    context["_attempt"] = attempt

    api = os.environ.get("CLAUDE_TASKS_API", "")
    if not api:
        print("ERROR: CLAUDE_TASKS_API not set", file=sys.stderr)
        return EXIT_ERROR

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
    return EXIT_ERROR


def cmd_write_env(args: Namespace) -> int:
    """Regenerate .eigen/env from .claude/settings.json."""
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return EXIT_ERROR

    settings_path = Path(root) / ".claude" / "settings.json"
    if not settings_path.exists():
        print(f"ERROR: {settings_path} not found", file=sys.stderr)
        return EXIT_ERROR

    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Failed to read settings: {e}", file=sys.stderr)
        return EXIT_ERROR

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
