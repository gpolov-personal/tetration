"""Git operations for pipeline state management.

Centralizes all git sync, commit, push, and branch operations that were
previously scattered across every command prompt.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(args: list[str], cwd: str = "", check: bool = False) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=cwd or None,
        capture_output=True,
        text=True,
        check=check,
    )


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
) -> bool:
    """Checkout a branch, optionally creating it.

    Returns True if checkout succeeded.
    """
    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)

    result = run_git(args, cwd=eigen_root)
    if result.returncode != 0 and not create:
        # Try fetching first then retry
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
        state_file: Path to pipeline_state.json (relative to eigen_root).
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

    # Stage files
    result = run_git(["add"] + paths_to_add, cwd=eigen_root)
    if result.returncode != 0:
        return False

    # Check if there's anything to commit
    status = run_git(["diff", "--cached", "--quiet"], cwd=eigen_root)
    if status.returncode == 0:
        # Nothing staged — skip commit
        return True

    # Commit
    result = run_git(["commit", "-m", message], cwd=eigen_root)
    if result.returncode != 0:
        return False

    # Push
    push_branch = branch or current_branch(eigen_root)
    if push_branch:
        result = run_git(["push", "origin", push_branch], cwd=eigen_root)
        return result.returncode == 0

    return True


def integration_branch_name(phase: int, epic: int) -> str:
    """Generate the integration branch name for a phase/epic."""
    return f"feat/P{phase}.E{epic}"
