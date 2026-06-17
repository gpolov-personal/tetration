"""Squared-specific scheduler shim.

Skill resolution and task-name formatting are squared-specific; the wire
protocol (curl POST + JSONL log + retry detection) lives in eigen-core.
This module preserves the ``cli.scheduler`` import path used by
subcommands and tests, plus the ``schedule_command(command, context, ...)``
signature that callers depend on.
"""

from __future__ import annotations

from pathlib import Path

from eigen_core.cli.scheduler import (  # noqa: F401  (re-exported for callers/tests)
    DEDUP_WINDOW_SECONDS,
    MAX_COMMAND_RETRIES,
    MAX_SCHEDULE_FAILURES,
    SCHEDULE_DELAY_MINUTES,
    alert,
    check_retry,
    consecutive_schedule_failures,
    last_confirmed_entry,
    log_entry,
    resolve_hook_log as _core_resolve_hook_log,
    schedule_command as _core_schedule_command,
)


COMMAND_TO_SKILL = {
    "time_split": "eigen-squared:time_split",
    "bootstrap_converge": "eigen-squared:bootstrap_converge",
    "space_split_converge": "eigen-squared:space_split_converge",
    "plan_epic_converge": "eigen-squared:plan_epic_converge",
    "create_issues_from_plan_swarm": "eigen-squared:create_issues_from_plan_swarm",
    "orchestrate_swarm": "eigen-squared:orchestrate_swarm",
    "review_swarm_pr": "eigen-squared:review_swarm_pr",
}


# Per-command execution profile: (model, effort) for `claude -p --model
# --effort`. One row per command so the model and reasoning effort each step
# runs on are visible at a glance. Edit a row to retune a step (e.g. a cheaper
# model for mechanical steps). An empty string in either slot omits that flag,
# so claude-tasks / Claude Code falls back to the global default. Pinning the
# model here prevents unsupervised runs from silently using whatever
# interactive default happens to be set.
DEFAULT_MODEL = "claude-opus-4-8[1m]"
EXECUTION_BY_COMMAND = {
    # command                          (model,         effort)
    "time_split":                      (DEFAULT_MODEL, "xhigh"),
    "bootstrap_converge":              (DEFAULT_MODEL, "high"),
    "space_split_converge":            (DEFAULT_MODEL, "medium"),
    "plan_epic_converge":              (DEFAULT_MODEL, "medium"),
    "create_issues_from_plan_swarm":   (DEFAULT_MODEL, "low"),
    "orchestrate_swarm":               (DEFAULT_MODEL, "low"),
    "review_swarm_pr":                 (DEFAULT_MODEL, "low"),
}


def resolve_hook_log(eigen_root: str) -> Path:
    return _core_resolve_hook_log(eigen_root, dot_dir=".eigen")


def _format_task_name(command: str, context: dict) -> str:
    scope = context.get("scope", "")
    phase = context.get("phase")
    epic = context.get("epic")
    if scope == "initiative":
        return f"eigen: {command}"
    if scope == "phase":
        return f"eigen: {command} P{phase}"
    return f"eigen: {command} P{phase}.E{epic}"


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
    """Resolve squared-specific skill + task name, then delegate to core."""
    skill = COMMAND_TO_SKILL.get(command, "")
    if not skill:
        return False

    from .transitions import make_context_key

    model, effort = EXECUTION_BY_COMMAND.get(command, ("", ""))

    return _core_schedule_command(
        command,
        skill=skill,
        task_name=_format_task_name(command, context),
        context_key=make_context_key(context),
        eigen_root=eigen_root,
        claude_tasks_api=claude_tasks_api,
        hook_log=hook_log,
        delay_minutes=delay_minutes,
        extra_prompt=extra_prompt,
        telegram_chat_id=telegram_chat_id,
        slack_webhook=slack_webhook,
        discord_webhook=discord_webhook,
        effort=effort,
        model=model,
        attempt=context.get("_attempt", 1),
    )
