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


class TestIntegrationBranchName:
    def test_format(self):
        assert integration_branch_name(1, 2) == "feat/P1.E2"
        assert integration_branch_name(7, 13) == "feat/P7.E13"
