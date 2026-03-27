"""Task scheduling via claude-tasks API + retry logic + logging.

Ported from hooks/pipeline_controller.py (lines 79-662).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


MAX_COMMAND_RETRIES = 3
SCHEDULE_DELAY_MINUTES = 3

COMMAND_TO_SKILL = {
    "time_split": "eigen-squared:time_split",
    "deepen_time_split": "eigen-squared:deepen_time_split",
    "bootstrap": "eigen-squared:bootstrap",
    "deepen_bootstrap": "eigen-squared:deepen_bootstrap",
    "space_split": "eigen-squared:space_split",
    "deepen_space_split": "eigen-squared:deepen_space_split",
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


def check_retry(
    command: str, context_key: str, hook_log: Path
) -> tuple[bool, int]:
    """Check if we're retrying the same command.

    Returns (should_proceed, attempt).
    """
    last = last_confirmed_entry(hook_log)
    if last is None:
        return True, 1

    if last.get("command") == command and last.get("context_key") == context_key:
        attempt = last.get("attempt", 1) + 1
        if attempt > MAX_COMMAND_RETRIES:
            log_entry(
                hook_log,
                {
                    "action": "stalled",
                    "command": command,
                    "context_key": context_key,
                    "status": "stalled",
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

    payload: dict = {
        "name": task_name,
        "prompt": (
            f'Use the Skill tool to invoke Skill("{skill}"). '
            f"Follow all its instructions completely."
        ),
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
                "curl", "-s", "-X", "POST",
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
        log_entry(
            hook_log,
            {
                "action": "schedule_failed",
                "command": command,
                "context_key": context_key,
                "status": "failed",
            },
        )

    return success


def alert(level: str, message: str, hook_log: Path) -> None:
    """Log an alert."""
    log_entry(hook_log, {"action": "alert", "level": level, "message": message})
