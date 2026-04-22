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
    """Pull latest from remote branch, refusing non-fast-forward merges.

    1.5 — uses ``--ff-only`` so a diverged local branch fails loudly
    instead of producing a silent merge commit. True on fast-forward or
    already-up-to-date; False on any other outcome (network failure,
    auth, divergence). The failure path is surfaced via run_git's
    stderr propagation (1.7).
    """
    result = run_git(
        ["pull", "--ff-only", "origin", branch, "--quiet"],
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

    Preconditions and error semantics (1.10):

    * **Clean working tree required.** If `git status --porcelain` reports
      any untracked/uncommitted changes, refuse the checkout with a clear
      stderr message rather than silently carrying changes across branches.
    * **create=True refuses collisions.** If the branch already exists
      either locally or on ``origin/``, abort loudly instead of falling
      through to a silent re-checkout of an existing branch (the old
      behavior leaked partial side-effects from the `checkout base` +
      `pull base` that precede the `-b`).
    * **create=False with fetch fallback.** If a direct checkout fails,
      try `fetch origin <branch>` once and retry. On second failure,
      distinguish "branch does not exist on origin" (via `ls-remote
      --exit-code`) from network/auth errors and emit a differentiated
      stderr message.

    Returns True on success, False on any refused or failed step. Failure
    reasons are always surfaced to sys.stderr so invoking callers see why.
    """
    # 1. Clean-tree precondition — never carry uncommitted work across branches.
    dirty = run_git(["status", "--porcelain"], cwd=eigen_root, silent=True)
    if dirty.returncode == 0 and dirty.stdout.strip():
        sys.stderr.write(
            f"[checkout_branch] refusing to checkout '{branch}': working "
            "tree has uncommitted changes. Commit, stash, or reset first.\n"
        )
        return False

    if create:
        # 2. Branch must not already exist anywhere when creating.
        local_exists = (
            run_git(
                ["rev-parse", "--verify", f"refs/heads/{branch}"],
                cwd=eigen_root,
                silent=True,
            ).returncode
            == 0
        )
        remote_exists = (
            run_git(
                ["rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
                cwd=eigen_root,
                silent=True,
            ).returncode
            == 0
        )
        if local_exists or remote_exists:
            where = " and ".join(
                part
                for part, flag in (("local", local_exists), ("origin", remote_exists))
                if flag
            )
            sys.stderr.write(
                f"[checkout_branch] refusing to create '{branch}': already "
                f"exists ({where}). Delete it first or call with create=False.\n"
            )
            return False

        if base_branch:
            # Switch to base and pull it (ff-only) so the new branch starts
            # from a remote-synced tip. Failures here are fatal for create.
            base_checkout = run_git(["checkout", base_branch], cwd=eigen_root)
            if base_checkout.returncode != 0:
                return False
            base_pull = run_git(
                ["pull", "--ff-only", "origin", base_branch, "--quiet"],
                cwd=eigen_root,
            )
            if base_pull.returncode != 0:
                return False

        # Finally, create the new branch.
        return run_git(["checkout", "-b", branch], cwd=eigen_root).returncode == 0

    # create=False: try to switch to an existing branch.
    first = run_git(["checkout", branch], cwd=eigen_root, silent=True)
    if first.returncode == 0:
        return True

    # Local checkout failed — maybe we just haven't fetched the ref yet.
    fetched = run_git(["fetch", "origin", branch, "--quiet"], cwd=eigen_root, silent=True)
    if fetched.returncode != 0:
        # ls-remote --exit-code returns 2 when the ref is missing on origin
        # (as opposed to a network/auth error which usually returns 128).
        probe = run_git(
            ["ls-remote", "--exit-code", "--heads", "origin", branch],
            cwd=eigen_root,
            silent=True,
        )
        if probe.returncode == 2:
            sys.stderr.write(
                f"[checkout_branch] branch '{branch}' does not exist "
                "locally or on origin.\n"
            )
        else:
            sys.stderr.write(
                f"[checkout_branch] fetch of 'origin/{branch}' failed: "
                f"{fetched.stderr.strip() or probe.stderr.strip()}\n"
            )
        return False

    # Fetch succeeded; retry checkout, now noisily so the real reason shows.
    return run_git(["checkout", branch], cwd=eigen_root).returncode == 0


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

    # 1.4 — refuse to silently skip the push when we cannot resolve a real
    # branch to push to. Previously an empty current_branch (rev-parse
    # failure) or "HEAD" (detached HEAD) made commit_state return True
    # without pushing, leaving the remote behind and the pipeline state
    # on the feature branch only — exactly the shape that let P2.E1 land
    # its CONVERGED commit on an ephemeral local branch before the squash
    # collapsed it. If the caller has no legitimate target, surface it.
    push_branch = branch or current_branch(eigen_root)
    if not push_branch or push_branch == "HEAD":
        sys.stderr.write(
            "[commit_state] refusing to push: no branch resolved "
            f"(current_branch={push_branch!r}). The commit landed locally "
            "but was NOT pushed — call commit_state with an explicit "
            "branch= or check out a named branch before committing.\n"
        )
        return False

    result = run_git(["push", "origin", push_branch], cwd=eigen_root)
    return result.returncode == 0


def integration_branch_name(phase: int, epic: int) -> str:
    """Generate the integration branch name for a phase/epic."""
    return f"feat/P{phase}.E{epic}"
