"""Integration plumbing subcommands: git operations, claude-tasks scheduling,
environment file management. Separated from core state handlers to keep
``subcommands/__init__.py`` focused on state mutations.

Every handler here returns an exit code (int). Register them with
``register_handler`` from ``subcommands/__init__.py`` so ``dispatch()`` picks
them up.
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from pathlib import Path

from eigen_core.cli import git_ops
from eigen_core.cli.scheduler import (
    MAX_COMMAND_RETRIES,
    check_retry,
    log_entry as sched_log_entry,
    resolve_hook_log,
    schedule_command as core_schedule_command,
)

from .subcommands import (
    _eigen_branch,
    _eigen_root,
    _load_or_die,
    _resolve_state_path,
    register_handler,
)
from .transitions_lite import (
    determine_next_lite,
    make_context_key_lite,
    resolve_branch_lite,
)


LITE_DOT_DIR = ".eigen-lite"

COMMAND_TO_SKILL_LITE = {
    "lite_plan": "eigen-lite:lite_plan",
    "lite_swarm": "eigen-lite:lite_swarm",
    "lite_review": "eigen-lite:lite_review",
}


def _format_task_name(command: str, context: dict) -> str:
    """Mirror squared's naming scheme but drop the phase prefix — lite is
    always single-phase so P1 is implicit."""
    scope = context.get("scope", "")
    epic = context.get("epic")
    if scope == "initiative":
        return f"eigen-lite: {command}"
    if epic is not None:
        return f"eigen-lite: {command} E{epic}"
    return f"eigen-lite: {command}"


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def cmd_sync(args: Namespace) -> int:
    branch = getattr(args, "branch", None) or _eigen_branch()
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return 1
    ok = git_ops.sync(branch, root)
    if not ok:
        print(json.dumps({"status": "failed", "branch": branch}),
              file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "branch": branch}))
    return 0


# ---------------------------------------------------------------------------
# commit-state
# ---------------------------------------------------------------------------

def cmd_commit_state(args: Namespace) -> int:
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return 1

    state_path = _resolve_state_path(args)
    additional = []
    if getattr(args, "additional_paths", None):
        additional = [p.strip() for p in args.additional_paths.split(",") if p.strip()]

    ok = git_ops.commit_state(
        message=args.message,
        eigen_root=root,
        state_file=state_path,
        additional_paths=additional,
        branch=getattr(args, "branch", None) or "",
    )
    if not ok:
        print(json.dumps({"status": "failed"}), file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok"}))
    return 0


# ---------------------------------------------------------------------------
# resolve-branch
# ---------------------------------------------------------------------------

def cmd_resolve_branch(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    branch = resolve_branch_lite(
        state.to_dict(),
        eigen_branch=_eigen_branch(),
    )
    if getattr(args, "as_json", False):
        print(json.dumps({"branch": branch}))
    else:
        print(branch)
    return 0


# ---------------------------------------------------------------------------
# checkout-branch
# ---------------------------------------------------------------------------

def cmd_checkout_branch(args: Namespace) -> int:
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return 1
    branch = git_ops.integration_branch_name(1, args.epic)
    ok = git_ops.checkout_branch(
        branch,
        eigen_root=root,
        create=getattr(args, "create", False),
        base_branch=_eigen_branch() if getattr(args, "create", False) else "",
    )
    if not ok:
        print(json.dumps({"status": "failed", "branch": branch}),
              file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "branch": branch}))
    return 0


# ---------------------------------------------------------------------------
# write-env / install
# ---------------------------------------------------------------------------

def cmd_write_env(args: Namespace) -> int:
    """Regenerate .eigen-lite/env from the current process environment.

    The watchdog shell script sources this file on every tick; writing it
    from the CLI (rather than having the watchdog parse settings.json)
    keeps the shell script small.
    """
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return 1
    env_path = Path(root) / LITE_DOT_DIR / "env"
    env_path.parent.mkdir(parents=True, exist_ok=True)

    keys = [
        "EIGEN_ROOT",
        "EIGEN_BRANCH",
        "CLAUDE_TASKS_API",
        "EIGEN_TELEGRAM_CHAT_ID",
        "EIGEN_SLACK_WEBHOOK",
        "EIGEN_DISCORD_WEBHOOK",
    ]
    lines = [
        f'{k}="{os.environ[k]}"'
        for k in keys
        if os.environ.get(k)
    ]
    env_path.write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": "ok", "env_file": str(env_path)}))
    return 0


def cmd_install(args: Namespace) -> int:
    """One-time setup: create .eigen-lite/ with initial env file.

    Watchdog installation (cron entry, binary symlink) is intentionally NOT
    automated here — Sprint 3 wires up the watchdog script separately once
    we have a real integration test harness to validate it against.
    """
    root = Path(args.root).resolve()
    dot_dir = root / LITE_DOT_DIR
    dot_dir.mkdir(parents=True, exist_ok=True)

    env_path = dot_dir / "env"
    env_lines = [
        f'EIGEN_ROOT="{root}"',
        f'EIGEN_BRANCH="{args.branch}"',
        f'CLAUDE_TASKS_API="{args.tasks_api}"',
    ]
    if getattr(args, "telegram", None):
        env_lines.append(f'EIGEN_TELEGRAM_CHAT_ID="{args.telegram}"')
    if getattr(args, "slack", None):
        env_lines.append(f'EIGEN_SLACK_WEBHOOK="{args.slack}"')
    if getattr(args, "discord", None):
        env_lines.append(f'EIGEN_DISCORD_WEBHOOK="{args.discord}"')

    env_path.write_text("\n".join(env_lines) + "\n")
    print(json.dumps({
        "status": "ok",
        "dot_dir": str(dot_dir),
        "env_file": str(env_path),
    }))
    return 0


# ---------------------------------------------------------------------------
# schedule-next
# ---------------------------------------------------------------------------

def cmd_schedule_next(args: Namespace) -> int:
    state, _ = _load_or_die(args)
    root = _eigen_root()
    if not root:
        print("ERROR: EIGEN_ROOT not set", file=sys.stderr)
        return 1

    hook_log = resolve_hook_log(root, dot_dir=LITE_DOT_DIR)
    result = determine_next_lite(state.to_dict())

    if result is None:
        sched_log_entry(hook_log, {
            "action": "noop",
            "command": None,
            "context_key": None,
            "status": "noop",
            "reason": "pipeline complete",
        })
        return 0

    command, context = result
    context_key = make_context_key_lite(context)

    proceed, attempt = check_retry(command, context_key, hook_log)
    if not proceed:
        if attempt > MAX_COMMAND_RETRIES:
            print(
                json.dumps({
                    "status": "stalled",
                    "command": command,
                    "context_key": context_key,
                    "attempt": attempt,
                }),
                file=sys.stderr,
            )
            return 2
        return 0  # dedup — not an error

    api = os.environ.get("CLAUDE_TASKS_API", "")
    if not api:
        print("ERROR: CLAUDE_TASKS_API not set", file=sys.stderr)
        return 1

    skill = COMMAND_TO_SKILL_LITE.get(command, "")
    if not skill:
        print(f"ERROR: no skill mapping for {command!r}", file=sys.stderr)
        return 1

    success = core_schedule_command(
        command,
        skill=skill,
        task_name=_format_task_name(command, context),
        context_key=context_key,
        eigen_root=root,
        claude_tasks_api=api,
        hook_log=hook_log,
        delay_minutes=getattr(args, "delay_minutes", 1),
        extra_prompt=getattr(args, "extra_prompt", "") or "",
        telegram_chat_id=os.environ.get("EIGEN_TELEGRAM_CHAT_ID", ""),
        slack_webhook=os.environ.get("EIGEN_SLACK_WEBHOOK", ""),
        discord_webhook=os.environ.get("EIGEN_DISCORD_WEBHOOK", ""),
        attempt=attempt,
    )
    return 0 if success else 1


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_all() -> None:
    register_handler("sync", cmd_sync)
    register_handler("commit-state", cmd_commit_state)
    register_handler("resolve-branch", cmd_resolve_branch)
    register_handler("checkout-branch", cmd_checkout_branch)
    register_handler("write-env", cmd_write_env)
    register_handler("install", cmd_install)
    register_handler("schedule-next", cmd_schedule_next)


# Self-register on import so main.py only needs `import cli.plumbing` (done
# below in the dispatcher wiring).
register_all()
