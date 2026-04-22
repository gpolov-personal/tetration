"""Tests for git_ops — exercise on a real temporary git repo (no mocks)."""

import subprocess

import pytest

from eigen_core.cli.git_ops import (
    checkout_branch,
    commit_state,
    current_branch,
    integration_branch_name,
    run_git,
)


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(["init", "-q", "-b", "main"], cwd=tmp_path)
    _git(["config", "user.email", "test@example.com"], cwd=tmp_path)
    _git(["config", "user.name", "Test"], cwd=tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _git(["add", "seed.txt"], cwd=tmp_path)
    _git(["commit", "-q", "-m", "seed"], cwd=tmp_path)
    return tmp_path


class TestCurrentBranch:
    def test_returns_active_branch(self, repo):
        assert current_branch(str(repo)) == "main"

    def test_empty_for_non_repo(self, tmp_path):
        assert current_branch(str(tmp_path)) == ""


class TestCheckoutBranch:
    def test_creates_new_branch(self, repo):
        assert checkout_branch("feat/test", str(repo), create=True) is True
        assert current_branch(str(repo)) == "feat/test"

    def test_switches_existing_branch(self, repo):
        _git(["checkout", "-q", "-b", "feature"], cwd=repo)
        _git(["checkout", "-q", "main"], cwd=repo)
        assert checkout_branch("feature", str(repo)) is True
        assert current_branch(str(repo)) == "feature"

    # --- 1.10: create-collision refused ---

    def test_create_refused_when_branch_exists_locally(self, repo, capsys):
        _git(["checkout", "-q", "-b", "feat/existing"], cwd=repo)
        _git(["checkout", "-q", "main"], cwd=repo)
        assert checkout_branch("feat/existing", str(repo), create=True) is False
        captured = capsys.readouterr()
        assert "already exists" in captured.err
        assert "local" in captured.err

    # --- 1.10: missing branch reports a clear error ---

    def test_checkout_missing_branch_reports_not_found(self, repo, capsys):
        # No remote configured — ls-remote probe returns 128, so the
        # message falls into the "fetch failed" bucket rather than
        # "not found on origin". Either way, the branch clearly does not
        # exist locally, and the returned bool is False.
        assert checkout_branch("feat/nowhere", str(repo)) is False
        captured = capsys.readouterr()
        assert "feat/nowhere" in captured.err
        assert current_branch(str(repo)) == "main"


class TestCommitState:
    def test_no_paths_returns_false(self, repo):
        assert commit_state("msg", str(repo)) is False

    def test_commits_state_file(self, repo):
        state = repo / "state.json"
        state.write_text('{"ok": true}')
        # No remote — push will fail; that's fine for this isolated test.
        # We assert that commit happened by checking git log.
        commit_state("save", str(repo), state_file="state.json")
        log = run_git(["log", "--oneline"], cwd=str(repo)).stdout
        assert "save" in log

    def test_skips_commit_when_nothing_staged(self, repo):
        state = repo / "state.json"
        state.write_text('{"ok": true}')
        _git(["add", "state.json"], cwd=repo)
        _git(["commit", "-q", "-m", "first"], cwd=repo)
        # No changes since last commit — commit_state should still return True
        # (the no-op path).
        assert commit_state("noop", str(repo), state_file="state.json") is True

    # --- 1.4: detached HEAD / empty current_branch → refuse push ---

    def test_refuses_push_from_detached_head(self, repo, capsys):
        # Detach HEAD at the seed commit so current_branch() returns
        # "HEAD". commit_state must then refuse to push and return False.
        head_sha = run_git(["rev-parse", "HEAD"], cwd=str(repo)).stdout.strip()
        _git(["checkout", "-q", "--detach", head_sha], cwd=repo)
        state = repo / "state.json"
        state.write_text('{"ok": true}')
        assert commit_state("detached", str(repo), state_file="state.json") is False
        # The local commit still happened (we only refused the push).
        log = run_git(["log", "--oneline"], cwd=str(repo)).stdout
        assert "detached" in log
        captured = capsys.readouterr()
        assert "refusing to push" in captured.err
        assert "HEAD" in captured.err


class TestIntegrationBranchName:
    def test_format(self):
        assert integration_branch_name(1, 2) == "feat/P1.E2"
        assert integration_branch_name(7, 13) == "feat/P7.E13"


class TestRunGitErrorPropagation:
    """Failing git commands must surface their stderr to sys.stderr by default
    (1.7) so invoking callers see the real error instead of a silent bool.
    """

    def test_failure_emits_stderr_to_process_stderr(self, repo, capsys):
        result = run_git(["rev-parse", "--verify", "refs/heads/missing-branch"], cwd=str(repo))
        assert result.returncode != 0
        captured = capsys.readouterr()
        assert "[git rev-parse --verify refs/heads/missing-branch]" in captured.err

    def test_silent_suppresses_stderr(self, repo, capsys):
        result = run_git(
            ["rev-parse", "--verify", "refs/heads/missing-branch"],
            cwd=str(repo),
            silent=True,
        )
        assert result.returncode != 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_success_does_not_emit(self, repo, capsys):
        result = run_git(["rev-parse", "HEAD"], cwd=str(repo))
        assert result.returncode == 0
        captured = capsys.readouterr()
        assert captured.err == ""


class TestCredentialScrubbing:
    """S9 — git stderr sometimes echoes the full credential URL
    (``fatal: unable to access 'https://user:token@github.com/...'``).
    1.7 routes stderr to the process's sys.stderr where the claude-tasks
    transcript captures it, so scrubbing is required to keep tokens out
    of logs / prompts.
    """

    def test_scrub_user_colon_pass(self):
        from eigen_core.cli.git_ops import _scrub_credentials

        src = "fatal: unable to access 'https://alice:ghp_abcDEF123@github.com/org/repo/'"
        out = _scrub_credentials(src)
        assert "alice" not in out
        assert "ghp_abcDEF123" not in out
        assert "https://***@github.com/org/repo/" in out

    def test_scrub_token_only(self):
        """N3 — bare PAT token (20+ chars, no colon)."""
        from eigen_core.cli.git_ops import _scrub_credentials

        src = "fatal: cannot access 'https://ghp_PROD_TOKEN_ABCDEFG@github.com/org/repo'"
        out = _scrub_credentials(src)
        assert "ghp_PROD_TOKEN_ABCDEFG" not in out
        assert "https://***@github.com/org/repo" in out

    def test_scrub_password_only(self):
        """N3 — password-only form (:token@) used by git-credential-store."""
        from eigen_core.cli.git_ops import _scrub_credentials

        src = "fatal: cannot access 'https://:ghp_TOKEN@github.com/org/repo'"
        out = _scrub_credentials(src)
        assert "ghp_TOKEN" not in out
        assert "https://***@github.com/org/repo" in out

    def test_scrub_preserves_host_and_path(self):
        from eigen_core.cli.git_ops import _scrub_credentials

        out = _scrub_credentials("https://user:tok@example.com/path?q=v")
        assert out == "https://***@example.com/path?q=v"

    def test_scrub_leaves_non_credential_urls_alone(self):
        from eigen_core.cli.git_ops import _scrub_credentials

        src = "remote: https://github.com/org/repo"
        assert _scrub_credentials(src) == src

    def test_scrub_preserves_ssh_git_at(self):
        """B-R3-2 — ssh://git@github.com is a standard SSH principal,
        not a secret. Scrubbing it is a debugging regression."""
        from eigen_core.cli.git_ops import _scrub_credentials

        src = "fatal: could not read from 'ssh://git@github.com/org/repo.git'"
        assert _scrub_credentials(src) == src

    def test_scrub_applied_when_emitting_stderr(self, repo, capsys, monkeypatch):
        from eigen_core.cli import git_ops

        def _fake_run(*_a, **_kw):
            return subprocess.CompletedProcess(
                args=["git", "fetch"],
                returncode=128,
                stdout="",
                stderr="fatal: unable to access 'https://u:tok@github.com/x/y/'",
            )

        monkeypatch.setattr(subprocess, "run", _fake_run)
        result = git_ops.run_git(["fetch"], cwd=str(repo))
        assert result.returncode == 128
        captured = capsys.readouterr()
        assert "tok" not in captured.err
        assert "***@" in captured.err


class TestRunGitTimeout:
    """run_git must enforce a timeout (1.8) so a hung network call does
    not block the CLI indefinitely. Timeouts surface as returncode=124
    with a TIMEOUT marker on stderr.
    """

    def test_timeout_surfaces_as_rc_124(self, repo, capsys):
        # timeout=0 forces TimeoutExpired immediately on any git command
        # without requiring a real hung remote.
        result = run_git(["log", "--oneline"], cwd=str(repo), timeout=0)
        assert result.returncode == 124
        captured = capsys.readouterr()
        assert "TIMEOUT after 0s" in captured.err

    def test_timeout_silent_suppresses_stderr(self, repo, capsys):
        result = run_git(["log", "--oneline"], cwd=str(repo), timeout=0, silent=True)
        assert result.returncode == 124
        captured = capsys.readouterr()
        assert captured.err == ""
        # The synthesized CompletedProcess still carries the message
        # internally so programmatic callers can inspect it.
        assert "TIMEOUT" in result.stderr
