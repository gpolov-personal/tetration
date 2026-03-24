#!/usr/bin/env python3
"""
eigen-squared pipeline controller.

Fires on Claude Code "Stop" event via pipeline_hook.sh wrapper.
Reads pipeline_state.json, determines the next pipeline command, schedules it.

Two modes:
  --resolve-branch  Print the branch name the next command needs (fast, no side effects)
  --schedule        Determine next command, check retries, schedule via claude-tasks API
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

EIGEN_ROOT = os.environ.get("EIGEN_ROOT", "")
EIGEN_BRANCH = os.environ.get("EIGEN_BRANCH", "main")
CLAUDE_TASKS_API = os.environ.get("CLAUDE_TASKS_API", "")
# Notification config — optional, any of these may be set
TELEGRAM_CHAT_ID = os.environ.get("EIGEN_TELEGRAM_CHAT_ID")
SLACK_WEBHOOK = os.environ.get("EIGEN_SLACK_WEBHOOK")
DISCORD_WEBHOOK = os.environ.get("EIGEN_DISCORD_WEBHOOK")

STATE_FILE = Path(EIGEN_ROOT) / "eigen_initiative/phases/pipeline_state.json" if EIGEN_ROOT else Path()
HOOK_LOG = Path(EIGEN_ROOT) / ".eigen/hook_log.jsonl" if EIGEN_ROOT else Path()

MAX_COMMAND_RETRIES = 3
SCHEDULE_DELAY_MINUTES = 3

COMMAND_TO_SKILL = {
    "time_split": "eigen-squared:time_split",
    "deepen_time_split": "eigen-squared:deepen_time_split",
    "bootstrap": "eigen-squared:bootstrap",
    "deepen_bootstrap": "eigen-squared:deepen_bootstrap",
    "space_split": "eigen-squared:space_split",
    "deepen_space_split": "eigen-squared:deepen_space_split",
    "plan_phase_epic": "eigen-squared:plan_phase_epic",
    "deepen_plan_phase_epic": "eigen-squared:deepen_plan_phase_epic",
    "create_issues_from_plan_swarm": "eigen-squared:create_issues_from_plan_swarm",
    "orchestrate_swarm": "eigen-squared:orchestrate_swarm",
    "review_swarm_pr": "eigen-squared:review_swarm_pr",
}

# Commands that run on integration branches (feat/P<N>.E<M>)
INTEGRATION_BRANCH_COMMANDS = {"orchestrate_swarm", "review_swarm_pr"}


# ─────────────────────────────────────────────────────────────────────────────
# STATE LOADING
# ─────────────────────────────────────────────────────────────────────────────

def load_state():
    """Read pipeline_state.json from filesystem.

    The bash wrapper (pipeline_hook.sh) ensures we're on the correct branch
    before this is called, so reading from the filesystem is always correct.
    """
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING — Two-phase (pending → confirmed/failed)
# ─────────────────────────────────────────────────────────────────────────────

def log_entry(entry):
    """Append a JSON line to hook_log.jsonl."""
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    HOOK_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HOOK_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def last_confirmed_entry():
    """Read the most recent 'confirmed' entry with a command from hook_log.

    Only returns entries that have both 'status'='confirmed' AND a 'command' field.
    This excludes noop entries which have status=confirmed but no command.
    Reads only the last 8KB of the file to avoid O(n) full-file reads on large logs.
    """
    if not HOOK_LOG.exists():
        return None
    try:
        file_size = HOOK_LOG.stat().st_size
        with open(HOOK_LOG, "r") as f:
            # Read last 8KB (enough for ~40 entries)
            read_from = max(0, file_size - 8192)
            f.seek(read_from)
            if read_from > 0:
                f.readline()  # Discard partial first line
            tail = f.read()
        for line in reversed(tail.strip().split("\n")):
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("status") == "confirmed" and entry.get("command"):
                    return entry
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return None


def is_recently_scheduled(command, context_key):
    """Check if this command+context was already scheduled within the delay window.

    Scans recent log entries for a 'confirmed' scheduling of the same command
    and context_key that is still within SCHEDULE_DELAY_MINUTES (i.e., the
    scheduled task hasn't had time to run yet). Prevents duplicate task creation
    when multiple Stop events fire in quick succession.

    Returns True if a duplicate exists and scheduling should be skipped.
    """
    if not HOOK_LOG.exists():
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SCHEDULE_DELAY_MINUTES)
    try:
        file_size = HOOK_LOG.stat().st_size
        with open(HOOK_LOG, "r") as f:
            read_from = max(0, file_size - 8192)
            f.seek(read_from)
            if read_from > 0:
                f.readline()
            tail = f.read()
        for line in reversed(tail.strip().split("\n")):
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Only check confirmed scheduling entries
            if entry.get("status") != "confirmed" or entry.get("action") != "scheduled":
                continue
            # Check if it's the same command+context
            if entry.get("command") != command or entry.get("context_key") != context_key:
                continue
            # Check if it's within the delay window
            ts = entry.get("timestamp", "")
            try:
                entry_time = datetime.fromisoformat(ts)
                if entry_time > cutoff:
                    return True  # Recently scheduled — skip
            except (ValueError, TypeError):
                continue
    except OSError:
        pass
    return False


def check_retry(command, context_key):
    """Check if we're retrying the same command.

    Compares against the last confirmed log entry. If the same command with
    the same context_key was scheduled last time, this is a retry (the command
    ran but didn't change state).

    Returns:
        (should_proceed: bool, attempt: int)
    """
    last = last_confirmed_entry()
    if last is None:
        return True, 1

    if last.get("command") == command and last.get("context_key") == context_key:
        attempt = last.get("attempt", 1) + 1
        if attempt > MAX_COMMAND_RETRIES:
            alert(
                "error",
                f"Pipeline stalled: {command} ({context_key}) failed "
                f"{MAX_COMMAND_RETRIES} times. Manual intervention required.",
            )
            log_entry(
                {
                    "action": "stalled",
                    "command": command,
                    "context_key": context_key,
                    "status": "stalled",
                }
            )
            return False, attempt
        return True, attempt

    return True, 1  # Different command — reset attempt counter


# ─────────────────────────────────────────────────────────────────────────────
# CONVERGENCE PAIR LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def next_for_convergence_pair(main_state, deepen_state):
    """Determine next action for a main/deepen command pair.

    Works for all convergence pairs:
      time_split ↔ deepen_time_split
      bootstrap ↔ deepen_bootstrap
      space_split ↔ deepen_space_split
      plan_phase_epic ↔ deepen_plan_phase_epic

    The lifecycle is:
      1. main runs (first time) → sets own fc=false, deepen fc=true
      2. deepen runs → sets main fc=false (fresh feedback), own fc=false
      3. main runs again → reads feedback, sets own fc=true, deepen fc=true
      4. deepen runs again → ... cycle until convergence

    Returns:
        ("run_main", reason) | ("run_deepen", reason) | ("converged", reason)
    """
    main_status = main_state.get("status", "not_started")
    main_converged = main_state.get("convergence", {}).get("converged", False)
    main_fc = main_state.get("feedback_consumed", False)
    deepen_status = deepen_state.get("status", "not_started")

    # Already converged — done with this pair
    if main_converged:
        return ("converged", "already converged")

    # Main never ran — run it
    if main_status == "not_started":
        return ("run_main", "first run")

    # Main has run at least once — check if deepen needs to run
    if deepen_status == "not_started":
        return ("run_deepen", "main completed, deepen not started")

    # Both have run at least once — check feedback cycle
    if not main_fc:
        # Fresh feedback available — main should consume it
        return ("run_main", "fresh feedback available from deepen")

    # main_fc is True — main consumed feedback, deepen needs to re-analyze
    # This covers ALL remaining states (including deepen_fc=True and deepen_fc=False)
    return ("run_deepen", "main processed feedback, deepen needs re-analysis")


def next_for_swarm_pair(swarm_state):
    """Determine next action for orchestrate_swarm / review_swarm_pr.

    review_swarm_pr decides convergence (same role as deepen commands).

    The lifecycle is:
      1. orchestrate_swarm creates PR → status = "pr_created"
      2. review_swarm_pr reviews → if findings: status = "iterating", creates fixup tasks
      3. review_swarm_pr reviews → if no findings: convergence.converged = true
      4. orchestrate_swarm runs fixups → status = "pr_created" (PR updated)
      5. review_swarm_pr reviews again → etc.

    Returns:
        ("run_orchestrate", reason) | ("run_review", reason) | ("converged", reason)
    """
    status = swarm_state.get("status", "not_started")
    converged = swarm_state.get("convergence", {}).get("converged", False)

    # Converged — done
    if converged:
        return ("converged", "swarm converged")

    # Never started — run orchestrate
    if status == "not_started":
        return ("run_orchestrate", "first run")

    # PR exists (freshly created or updated with fixups) — ALWAYS review.
    # This is critical: after orchestrate runs fixups and sets status back to
    # "pr_created", the next step is review, NOT another orchestrate.
    if status == "pr_created":
        return ("run_review", "PR ready for review")

    # Review found issues, fixup tasks created — orchestrate runs fixups
    if status == "iterating":
        return ("run_orchestrate", "fixup tasks pending")

    # Inconsistent: status field says "converged" but convergence.converged is false
    if status == "converged":
        return ("converged", "status says converged (trusting status field)")

    return ("run_review", "unknown swarm state, defaulting to review")


# ─────────────────────────────────────────────────────────────────────────────
# DETERMINE NEXT ACTION — Walk the pipeline state
# ─────────────────────────────────────────────────────────────────────────────

def determine_next(state):
    """Walk pipeline state in execution order and return the next command to run.

    Pipeline order:
      1. time_split ↔ deepen_time_split (once per initiative)
      2. Per phase (1, 2, ...):
         a. bootstrap ↔ deepen_bootstrap
         b. space_split ↔ deepen_space_split
         c. Per epic (in DAG wave order):
            i.   plan_phase_epic ↔ deepen_plan_phase_epic
            ii.  create_issues_from_plan_swarm (once, no deepen)
            iii. orchestrate_swarm ↔ review_swarm_pr
         d. All epics converged → STOP (human checkpoint via /eigen_continue)

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
        alert("error", "pipeline_state missing time_split or deepen_time_split")
        return None

    result = next_for_convergence_pair(ts, dts)
    if result[0] == "run_main":
        return ("time_split", {"scope": "initiative"})
    if result[0] == "run_deepen":
        return ("deepen_time_split", {"scope": "initiative"})

    # Validate phase_count (may be string from JSON)
    try:
        phase_count = int(ts.get("phase_count") or 0)
    except (ValueError, TypeError):
        phase_count = 0
    if phase_count == 0:
        alert("error", "time_split converged but phase_count is 0/null")
        return None

    # ── Per-phase stages ──

    for phase_num in range(1, phase_count + 1):
        phase_key = str(phase_num)
        phase = s.get("phases", {}).get(phase_key)

        if phase is None:
            alert("warning", f"Phase {phase_num} not initialized in pipeline state")
            return None

        # Phase already approved by human — skip to next phase
        phase_review = phase.get("phase_review", {})
        if phase_review.get("status") == "approved":
            continue

        # ── Bootstrap ↔ deepen_bootstrap (if this phase has these keys) ──

        if "bootstrap" in phase and "deepen_bootstrap" in phase:
            result = next_for_convergence_pair(
                phase["bootstrap"], phase["deepen_bootstrap"]
            )
            if result[0] == "run_main":
                return ("bootstrap", {"scope": "phase", "phase": phase_num})
            if result[0] == "run_deepen":
                return ("deepen_bootstrap", {"scope": "phase", "phase": phase_num})

        # ── Space_split ↔ deepen_space_split ──

        ss = phase.get("space_split")
        dss = phase.get("deepen_space_split")
        if not ss:
            alert("warning", f"Phase {phase_num} missing space_split state")
            return None
        if not dss:
            # deepen_space_split not yet initialized — run space_split first
            dss = {"status": "not_started", "feedback_consumed": False}

        result = next_for_convergence_pair(ss, dss)
        if result[0] == "run_main":
            return ("space_split", {"scope": "phase", "phase": phase_num})
        if result[0] == "run_deepen":
            return ("deepen_space_split", {"scope": "phase", "phase": phase_num})

        # ── Per-epic stages ──

        epic_order = load_epic_order(phase_num)
        if not epic_order:
            # epic_dag.json doesn't exist — space_split should have created it
            return ("space_split", {"scope": "phase", "phase": phase_num})

        all_epics_converged = True

        for epic_num in epic_order:
            epic_key = str(epic_num)
            plan = phase.get("plans", {}).get(epic_key)

            # Missing plan entry — this epic needs planning
            if plan is None:
                if epic_dependencies_met(phase, epic_num, phase_num):
                    return (
                        "plan_phase_epic",
                        {"scope": "epic", "phase": phase_num, "epic": epic_num},
                    )
                else:
                    all_epics_converged = False
                    continue  # Dependencies not met — can't start yet

            # ── Plan ↔ deepen_plan ──

            ppe = plan.get("plan_phase_epic")
            dppe = plan.get("deepen_plan_phase_epic")
            if not ppe:
                # Plan entry exists but sub-keys not populated — treat as not started
                if epic_dependencies_met(phase, epic_num, phase_num):
                    return (
                        "plan_phase_epic",
                        {"scope": "epic", "phase": phase_num, "epic": epic_num},
                    )
                else:
                    all_epics_converged = False
                    continue
            if not dppe:
                dppe = {"status": "not_started", "feedback_consumed": False}

            result = next_for_convergence_pair(ppe, dppe)
            if result[0] == "run_main":
                return (
                    "plan_phase_epic",
                    {"scope": "epic", "phase": phase_num, "epic": epic_num},
                )
            if result[0] == "run_deepen":
                return (
                    "deepen_plan_phase_epic",
                    {"scope": "epic", "phase": phase_num, "epic": epic_num},
                )

            # ── Create issues (inferred: no manifest = hasn't run) ──

            swarm = plan.get("swarm_execution", {})
            if (
                swarm.get("manifest_path") is None
                and swarm.get("status") == "not_started"
            ):
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
            # Phase complete — human checkpoint
            if phase_review.get("status") != "approved":
                if phase_review.get("status") == "not_started":
                    alert(
                        "info",
                        f"Phase {phase_num} complete! All epics converged. "
                        f"Run /eigen_continue to review and approve.",
                    )
                # Both "not_started" and "testing" = wait for human
                return None
        else:
            # Not all converged, but no actionable step was found in this phase.
            # This means epics are blocked on dependencies that aren't yet met.
            # Don't skip to the next phase — this phase isn't done.
            alert(
                "warning",
                f"Phase {phase_num}: epics have unmet dependencies. "
                f"Pipeline waiting for in-progress work to complete.",
            )
            return None

    # All phases approved
    alert("info", "All phases complete! Initiative finished.")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# BRANCH RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def resolve_branch(state):
    """Determine which git branch the next command should run on.

    - orchestrate_swarm and review_swarm_pr → integration branch (feat/P<N>.E<M>)
    - Everything else → EIGEN_BRANCH

    Returns:
        Branch name string, or empty string if no action needed.
    """
    result = determine_next(state)
    if result is None:
        return ""

    command, context = result

    if command in INTEGRATION_BRANCH_COMMANDS:
        branch = context.get("branch")
        if branch:
            return branch
        # Branch not yet known — shouldn't happen (create_issues sets it)
        return EIGEN_BRANCH

    return EIGEN_BRANCH


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_epic_order(phase_num):
    """Load epic execution order from epic_dag.json.

    Epics are returned in wave order: all wave-1 epics first, then wave-2, etc.
    """
    dag_path = (
        Path(EIGEN_ROOT)
        / f"eigen_initiative/phases/phase_{phase_num}/epic_dag.json"
    )
    if not dag_path.exists():
        return []
    try:
        dag = json.loads(dag_path.read_text())
        order = []
        for wave_key in sorted(dag.get("waves", {}).keys()):
            order.extend(dag["waves"][wave_key])
        return order
    except (json.JSONDecodeError, KeyError):
        return []


def epic_dependencies_met(phase, epic_num, phase_num):
    """Check if all of an epic's DAG dependencies (blocked_by) are converged."""
    dag_path = (
        Path(EIGEN_ROOT)
        / f"eigen_initiative/phases/phase_{phase_num}/epic_dag.json"
    )
    if not dag_path.exists():
        return False
    try:
        dag = json.loads(dag_path.read_text())
        for epic in dag.get("epics", []):
            if epic.get("number") == epic_num:
                for blocker_num in epic.get("blocked_by", []):
                    blocker = phase.get("plans", {}).get(str(blocker_num))
                    if blocker is None:
                        return False
                    swarm_converged = (
                        blocker.get("swarm_execution", {})
                        .get("convergence", {})
                        .get("converged", False)
                    )
                    if not swarm_converged:
                        return False
                return True  # All blockers converged (or no blockers)
        return False  # Epic not found in DAG
    except (json.JSONDecodeError, KeyError):
        return False


def make_context_key(context):
    """Build a semantic key for retry detection (no timestamps)."""
    parts = [context.get("scope", "unknown")]
    if "phase" in context:
        parts.append(f"P{context['phase']}")
    if "epic" in context:
        parts.append(f"E{context['epic']}")
    return ":".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULING
# ─────────────────────────────────────────────────────────────────────────────

def schedule_command(command, context):
    """Schedule a command via the claude-tasks API.

    Uses two-phase logging: logs "pending" before the curl, then "confirmed"
    or "failed" after. This prevents retry counter exhaustion on infra failures.

    Returns True if scheduling was confirmed.
    """
    skill = COMMAND_TO_SKILL[command]
    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=SCHEDULE_DELAY_MINUTES)
    ).isoformat()

    scope = context.get("scope", "")
    phase = context.get("phase")
    epic = context.get("epic")

    if scope == "initiative":
        task_name = f"eigen: {command}"
    elif scope == "phase":
        task_name = f"eigen: {command} P{phase}"
    else:
        task_name = f"eigen: {command} P{phase}.E{epic}"

    payload = {
        "name": task_name,
        "prompt": (
            f'Use the Skill tool to invoke Skill("{skill}"). '
            f"Follow all its instructions completely."
        ),
        "cron_expr": "",
        "scheduled_at": scheduled_at,
        "working_dir": EIGEN_ROOT,
        "enabled": True,
    }
    # Add notification config — only include what's configured
    if TELEGRAM_CHAT_ID:
        payload["telegram_webhook"] = TELEGRAM_CHAT_ID
    if SLACK_WEBHOOK:
        payload["slack_webhook"] = SLACK_WEBHOOK
    if DISCORD_WEBHOOK:
        payload["discord_webhook"] = DISCORD_WEBHOOK

    context_key = make_context_key(context)

    # Phase 1: log intent
    log_entry(
        {
            "action": "scheduling",
            "command": command,
            "context_key": context_key,
            "status": "pending",
        }
    )

    # Phase 2: execute
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                f"{CLAUDE_TASKS_API}/api/v1/tasks",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        success = result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        success = False

    # Phase 3: log outcome
    if success:
        log_entry(
            {
                "action": "scheduled",
                "command": command,
                "context_key": context_key,
                "status": "confirmed",
                "attempt": context.get("_attempt", 1),
                "task_name": task_name,
            }
        )
    else:
        log_entry(
            {
                "action": "schedule_failed",
                "command": command,
                "context_key": context_key,
                "status": "failed",
            }
        )

    return success


def alert(level, message):
    """Log an alert and send notification if configured."""
    log_entry({"action": "alert", "level": level, "message": message})
    # Future: send via telegram/slack/discord using TELEGRAM_CHAT_ID


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="eigen-squared pipeline controller"
    )
    parser.add_argument(
        "--resolve-branch",
        action="store_true",
        help="Print the target branch for the next command, then exit",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Determine and schedule the next pipeline command",
    )
    args = parser.parse_args()

    if not EIGEN_ROOT or not Path(EIGEN_ROOT).exists():
        sys.exit(0)

    state = load_state()
    if state is None:
        sys.exit(0)

    # ── Mode: resolve-branch (fast, no side effects) ──

    if args.resolve_branch:
        branch = resolve_branch(state)
        if branch:
            print(branch)
        return

    # ── Mode: schedule ──

    if args.schedule:
        result = determine_next(state)
        if result is None:
            log_entry(
                {
                    "action": "noop",
                    "command": None,
                    "context_key": None,
                    "status": "noop",
                    "reason": "human checkpoint or complete",
                }
            )
            return

        command, context = result
        context_key = make_context_key(context)

        # Verify branch consistency: if --resolve-branch ran first and the
        # bash wrapper checked out a different branch, the state we just read
        # may differ from what --resolve-branch saw. Verify the command we
        # picked is appropriate for the branch we're on.
        if command in INTEGRATION_BRANCH_COMMANDS:
            expected_branch = context.get("branch")
            if expected_branch:
                try:
                    actual = subprocess.run(
                        ["git", "-C", EIGEN_ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True, text=True
                    )
                    current = actual.stdout.strip()
                    if current and current != expected_branch:
                        alert(
                            "warning",
                            f"Branch mismatch: on {current}, expected {expected_branch} "
                            f"for {command}. Skipping — will self-correct next cycle.",
                        )
                        return
                except Exception:
                    pass  # Can't verify — proceed anyway

        # Dedup check: skip if same command was already scheduled recently
        if is_recently_scheduled(command, context_key):
            log_entry(
                {
                    "action": "dedup_skip",
                    "command": command,
                    "context_key": context_key,
                    "status": "skipped",
                    "reason": "already scheduled within delay window",
                }
            )
            return

        # Retry check
        should_proceed, attempt = check_retry(command, context_key)
        if not should_proceed:
            return
        context["_attempt"] = attempt

        # Schedule
        success = schedule_command(command, context)
        if not success:
            alert(
                "warning",
                f"Failed to schedule {command} ({context_key}). "
                f"Will retry on next Stop event.",
            )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
