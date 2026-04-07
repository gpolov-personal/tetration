"""Task scheduling via claude-tasks API + retry logic + logging.

Ported from hooks/pipeline_controller.py (lines 79-662).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


MAX_COMMAND_RETRIES = 4
MAX_SCHEDULE_FAILURES = 10
SCHEDULE_DELAY_MINUTES = 3
DEDUP_WINDOW_SECONDS = 30

COMMAND_TO_SKILL = {
    "time_split": "eigen-squared:time_split",
    "deepen_time_split": "eigen-squared:deepen_time_split",
    "bootstrap_converge": "eigen-squared:bootstrap_converge",
    "space_split_converge": "eigen-squared:space_split_converge",
    "plan_epic_converge": "eigen-squared:plan_epic_converge",
    "create_issues_from_plan_swarm": "eigen-squared:create_issues_from_plan_swarm",
    "orchestrate_swarm": "eigen-squared:orchestrate_swarm",
    "review_swarm_pr": "eigen-squared:review_swarm_pr",
}


def resolve_hook_log(eigen_root: str) -> Path:
    return Path(eigen_root) / ".eigen" / "hook_log.jsonl"


def log_entry(hook_log: Path, entry: dict) -> None:
    """Append a JSON line to hook_log.jsonl."""
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    hook_log.parent.mkdir(parents=True, exist_ok=True)
    with open(hook_log, "a") as f:
        f.write(json.dumps(entry) + "\n")


def last_confirmed_entry(hook_log: Path) -> Optional[dict]:
    """Read the most recent 'confirmed' entry with a command from hook_log.

    Only returns entries with both status='confirmed' AND a 'command' field.
    Reads only the last 8KB for efficiency.
    """
    if not hook_log.exists():
        return None
    try:
        file_size = hook_log.stat().st_size
        with open(hook_log, "r") as f:
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
                if entry.get("status") == "confirmed" and entry.get("command"):
                    return entry
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return None


def consecutive_schedule_failures(
    command: str, context_key: str, hook_log: Path
) -> int:
    """Count consecutive scheduling failures for a command+context.

    Reads the tail of hook_log and counts 'failed' entries in reverse
    until a non-failed entry (confirmed, skipped, stalled, noop) is found.
    """
    if not hook_log.exists():
        return 0
    count = 0
    try:
        file_size = hook_log.stat().st_size
        with open(hook_log, "r") as f:
            read_from = max(0, file_size - 16384)
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
            if entry.get("command") != command or entry.get("context_key") != context_key:
                continue
            if entry.get("status") in ("failed", "stalled"):
                count += 1
            else:
                break
    except OSError:
        pass
    return count


def check_retry(
    command: str, context_key: str, hook_log: Path
) -> tuple[bool, int]:
    """Check if we're retrying the same command.

    Returns (should_proceed, attempt).
    Deduplicates rapid-fire calls (< DEDUP_WINDOW_SECONDS) for the same
    command+context — these are duplicate schedule-next invocations within
    the same command execution, not genuine retries.

    Also checks for consecutive scheduling failures (API unreachable etc.)
    separately from task-execution retries. Scheduling failures use a higher
    threshold (MAX_SCHEDULE_FAILURES=10) since they're often transient.
    """
    # Check consecutive scheduling failures first
    sched_failures = consecutive_schedule_failures(command, context_key, hook_log)
    if sched_failures >= MAX_SCHEDULE_FAILURES:
        log_entry(
            hook_log,
            {
                "action": "stalled",
                "command": command,
                "context_key": context_key,
                "status": "stalled",
                "reason": f"scheduling failed {sched_failures} consecutive times",
                "consecutive_schedule_failures": sched_failures,
            },
        )
        return False, sched_failures

    last = last_confirmed_entry(hook_log)
    if last is None:
        return True, 1

    if last.get("command") == command and last.get("context_key") == context_key:
        # Check if this is a rapid duplicate (same execution) vs genuine retry
        last_ts = last.get("timestamp", "")
        try:
            last_time = datetime.fromisoformat(last_ts)
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            if elapsed < DEDUP_WINDOW_SECONDS:
                log_entry(
                    hook_log,
                    {
                        "action": "deduplicated",
                        "command": command,
                        "context_key": context_key,
                        "status": "skipped",
                    },
                )
                return False, last.get("attempt", 1)
        except (ValueError, TypeError):
            pass

        # Genuine retry — outside dedup window
        attempt = last.get("attempt", 1) + 1
        if attempt > MAX_COMMAND_RETRIES:
            log_entry(
                hook_log,
                {
                    "action": "stalled",
                    "command": command,
                    "context_key": context_key,
                    "status": "stalled",
                    "reason": f"task execution failed {attempt - 1} times (max {MAX_COMMAND_RETRIES})",
                },
            )
            return False, attempt
        return True, attempt

    return True, 1


def schedule_command(
    command: str,
    context: dict,
    *,
    eigen_root: str,
    claude_tasks_api: str,
    hook_log: Path,
    delay_minutes: int = SCHEDULE_DELAY_MINUTES,
    extra_prompt: str = "",
    telegram_chat_id: str = "",
    slack_webhook: str = "",
    discord_webhook: str = "",
) -> bool:
    """Schedule a command via the claude-tasks API.

    Uses two-phase logging: pending → confirmed/failed.
    Returns True if scheduling was confirmed.
    """
    skill = COMMAND_TO_SKILL.get(command)
    if not skill:
        return False

    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
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

    prompt = (
        f'Use the Skill tool to invoke Skill("{skill}"). '
        f"Follow all its instructions completely."
    )
    if extra_prompt:
        prompt += f"\n\n{extra_prompt}"

    payload: dict = {
        "name": task_name,
        "prompt": prompt,
        "cron_expr": "",
        "scheduled_at": scheduled_at,
        "working_dir": eigen_root,
        "enabled": True,
    }
    if telegram_chat_id:
        payload["telegram_webhook"] = telegram_chat_id
    if slack_webhook:
        payload["slack_webhook"] = slack_webhook
    if discord_webhook:
        payload["discord_webhook"] = discord_webhook

    from .transitions import make_context_key

    context_key = make_context_key(context)

    # Phase 1: log intent
    log_entry(
        hook_log,
        {
            "action": "scheduling",
            "command": command,
            "context_key": context_key,
            "status": "pending",
        },
    )

    # Phase 2: execute
    try:
        result = subprocess.run(
            [
                "curl", "-sf", "-X", "POST",
                f"{claude_tasks_api}/api/v1/tasks",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload),
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
            hook_log,
            {
                "action": "scheduled",
                "command": command,
                "context_key": context_key,
                "status": "confirmed",
                "attempt": context.get("_attempt", 1),
                "task_name": task_name,
            },
        )
    else:
        fail_count = consecutive_schedule_failures(command, context_key, hook_log) + 1
        log_entry(
            hook_log,
            {
                "action": "schedule_failed",
                "command": command,
                "context_key": context_key,
                "status": "failed",
                "consecutive_failures": fail_count,
                "max_schedule_failures": MAX_SCHEDULE_FAILURES,
                "task_name": task_name,
            },
        )

    return success


def alert(level: str, message: str, hook_log: Path) -> None:
    """Log an alert."""
    log_entry(hook_log, {"action": "alert", "level": level, "message": message})
