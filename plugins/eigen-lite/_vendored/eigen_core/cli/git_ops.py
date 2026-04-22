"""Git operations for pipeline state management.

Centralizes all git sync, commit, push, and branch operations that were
previously scattered across every command prompt.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


# Default timeouts (seconds) — enforced on every git invocation so a
# hung ssh handshake or unreachable remote cannot block the CLI forever.
# Network-touching verbs get a larger budget than local-only ones.
_DEFAULT_TIMEOUT = 30
_NETWORK_TIMEOUT = 120
_NETWORK_VERBS = {"pull", "push", "fetch", "clone", "ls-remote"}


def _timeout_for(args: list[str]) -> int:
    for arg in args:
        if arg in _NETWORK_VERBS:
            return _NETWORK_TIMEOUT
    return _DEFAULT_TIMEOUT


def run_git(
    args: list[str],
    cwd: str = "",
    check: bool = False,
    silent: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    """Run a git command and return the result.

    When the command fails (returncode != 0) and ``silent=False``, writes
    ``result.stderr`` to ``sys.stderr`` so the invoking caller (or the LLM
    that invoked the CLI) can see the actual git error instead of only a
    boolean. ``silent=True`` is for call-sites that use returncode as a
    condition check (e.g. ``git diff --quiet`` returns 1 when there are
    staged changes — not an error).

    ``timeout`` caps wall time. When omitted, a default is chosen based on
    the verb: 120s for network-touching commands (pull/push/fetch/...),
    30s otherwise. A timeout surfaces as returncode=124 + a stderr
    message so the failure is visible even when silent=False would
    otherwise be quiet.
    """
    cmd = ["git"] + args
    effective_timeout = timeout if timeout is not None else _timeout_for(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            check=check,
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"[git {' '.join(args)}] TIMEOUT after {effective_timeout}s"
        if not silent:
            sys.stderr.write(msg + "\n")
        # Synthesize a CompletedProcess-like result with returncode 124
        # (the conventional exit code used by coreutils `timeout(1)`).
        def _to_str(value: object) -> str:
            if value is None:
                return ""
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout=_to_str(exc.stdout),
            stderr=_to_str(exc.stderr) + msg,
        )
    if result.returncode != 0 and not silent:
        stderr = result.stderr.strip()
        if stderr:
            sys.stderr.write(f"[git {' '.join(args)}] {stderr}\n")
    return result


def sync(branch: str, eigen_root: str) -> bool:
    """Pull latest from remote branch.

    Returns True if pull succeeded.
    """
    result = run_git(
        ["pull", "origin", branch, "--quiet"],
        cwd=eigen_root,
    )
    return result.returncode == 0


def current_branch(eigen_root: str) -> str:
    """Get the current git branch name."""
    result = run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"],
        cwd=eigen_root,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def checkout_branch(
    branch: str,
    eigen_root: str,
    create: bool = False,
    base_branch: str = "",
) -> bool:
    """Checkout a branch, optionally creating it from base_branch.

    When create=True and base_branch is set, first checks out and pulls
    the base branch to ensure the new branch includes all prior work.

    Returns True if checkout succeeded.
    """
    if create and base_branch:
        run_git(["checkout", base_branch], cwd=eigen_root)
        run_git(["pull", "origin", base_branch, "--quiet"], cwd=eigen_root)

    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)

    result = run_git(args, cwd=eigen_root)
    if result.returncode != 0 and not create:
        run_git(["fetch", "origin", branch, "--quiet"], cwd=eigen_root)
        result = run_git(["checkout", branch], cwd=eigen_root)

    return result.returncode == 0


def commit_state(
    message: str,
    eigen_root: str,
    state_file: str | Path = "",
    additional_paths: list[str] | None = None,
    branch: str = "",
) -> bool:
    """Atomic git add + commit + push for pipeline state.

    Args:
        message: Commit message.
        eigen_root: Project root.
        state_file: Path to pipeline state file (relative to eigen_root).
        additional_paths: Extra paths to stage (relative to eigen_root).
        branch: Branch to push to (defaults to current branch).

    Returns True if all operations succeeded.
    """
    paths_to_add = []
    if state_file:
        rel = str(Path(state_file).relative_to(eigen_root)) if Path(state_file).is_absolute() else str(state_file)
        paths_to_add.append(rel)
    if additional_paths:
        paths_to_add.extend(additional_paths)

    if not paths_to_add:
        return False

    result = run_git(["add"] + paths_to_add, cwd=eigen_root)
    if result.returncode != 0:
        return False

    status = run_git(["diff", "--cached", "--quiet"], cwd=eigen_root, silent=True)
    if status.returncode == 0:
        return True

    result = run_git(["commit", "-m", message], cwd=eigen_root)
    if result.returncode != 0:
        return False

    push_branch = branch or current_branch(eigen_root)
    if push_branch:
        result = run_git(["push", "origin", push_branch], cwd=eigen_root)
        return result.returncode == 0

    return True


def integration_branch_name(phase: int, epic: int) -> str:
    """Generate the integration branch name for a phase/epic."""
    return f"feat/P{phase}.E{epic}"
