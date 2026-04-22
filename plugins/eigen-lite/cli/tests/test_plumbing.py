"""Tests for plumbing handlers (Batch C).

Uses real git + real filesystem — no mocks. schedule-next is tested via its
retry-detection + skill-resolution logic; the actual HTTP call is exercised
against a bogus URL and asserted to fail (integration with a live
claude-tasks API happens in Sprint 3).
"""

import json
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from cli.models_lite import (
    LiteConvergence,
    LiteEpicState,
    LitePipelineState,
    LiteSwarmExecution,
)
from cli.plumbing import (
    COMMAND_TO_SKILL_LITE,
    LITE_DOT_DIR,
    cmd_checkout_branch,
    cmd_commit_state,
    cmd_install,
    cmd_resolve_branch,
    cmd_schedule_next,
    cmd_sync,
    cmd_write_env,
)
from cli.state import create_initial_state, resolve_state_file, save_state


def _ns(**kwargs) -> Namespace:
    return Namespace(**kwargs)


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(["init", "-q", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _git(["add", "seed.txt"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    monkeypatch.setenv("EIGEN_ROOT", str(tmp_path))
    monkeypatch.setenv("EIGEN_BRANCH", "main")
    return tmp_path


@pytest.fixture
def repo_with_state(repo):
    path = resolve_state_file(repo)
    s = create_initial_state("my-init", epic_count=1)
    s.lite_plan.convergence = LiteConvergence(converged=True)
    s.lite_plan.stages_completed = ["A", "B", "C", "D", "E:1"]
    s.epics = {
        "1": LiteEpicState(
            epic_path="phases/phase_1/epic_1/",
            swarm_manifest="phases/phase_1/epic_1/swarm-manifest.json",
            lite_swarm=LiteSwarmExecution(integration_branch="feat/P1.E1"),
        ),
    }
    save_state(s, path)
    return repo, path


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

class TestCmdSync:
    def test_sync_without_eigen_root_fails(self, monkeypatch, capsys):
        monkeypatch.delenv("EIGEN_ROOT", raising=False)
        exit_code = cmd_sync(_ns(branch=None))
        assert exit_code == 1

    def test_sync_without_remote_fails(self, repo, capsys):
        """No remote configured → pull fails, we return 1."""
        exit_code = cmd_sync(_ns(branch="main"))
        assert exit_code == 1


# ---------------------------------------------------------------------------
# commit-state
# ---------------------------------------------------------------------------

class TestCmdCommitState:
    def test_commits_state_file(self, repo_with_state):
        root, path = repo_with_state
        # No remote — push will fail, commit-state returns 1
        # but the commit itself lands in the local tree. Verify via log.
        cmd_commit_state(_ns(
            state_file=str(path),
            message="test commit",
            additional_paths=None,
            branch=None,
        ))
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=root, capture_output=True, text=True,
        ).stdout
        assert "test commit" in log


# ---------------------------------------------------------------------------
# resolve-branch
# ---------------------------------------------------------------------------

class TestCmdResolveBranch:
    def test_returns_integration_branch_for_next_swarm(self, repo_with_state, capsys):
        _, path = repo_with_state
        cmd_resolve_branch(_ns(state_file=str(path), as_json=False))
        out = capsys.readouterr().out.strip()
        assert out == "feat/P1.E1"

    def test_json_output(self, repo_with_state, capsys):
        _, path = repo_with_state
        cmd_resolve_branch(_ns(state_file=str(path), as_json=True))
        out = json.loads(capsys.readouterr().out)
        assert out["branch"] == "feat/P1.E1"


# ---------------------------------------------------------------------------
# checkout-branch
# ---------------------------------------------------------------------------

class TestCmdCheckoutBranch:
    def test_create_switches_to_new_branch(self, repo):
        cmd_checkout_branch(_ns(epic=1, create=True))
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, capture_output=True, text=True,
        )
        assert result.stdout.strip() == "feat/P1.E1"


# ---------------------------------------------------------------------------
# write-env / install
# ---------------------------------------------------------------------------

class TestCmdWriteEnv:
    def test_writes_env_file_with_set_vars(self, repo, monkeypatch, capsys):
        monkeypatch.setenv("CLAUDE_TASKS_API", "http://localhost:8080")
        cmd_write_env(_ns())
        env_file = repo / LITE_DOT_DIR / "env"
        assert env_file.exists()
        contents = env_file.read_text()
        assert 'EIGEN_ROOT="' in contents
        assert 'CLAUDE_TASKS_API="http://localhost:8080"' in contents


class TestCmdInstall:
    def test_creates_dot_dir_and_env(self, tmp_path, capsys):
        cmd_install(_ns(
            root=str(tmp_path),
            branch="main",
            tasks_api="http://api.local",
            telegram=None,
            slack=None,
            discord=None,
        ))
        dot = tmp_path / LITE_DOT_DIR
        assert dot.exists()
        env = (dot / "env").read_text()
        assert f'EIGEN_ROOT="{tmp_path}"' in env
        assert 'CLAUDE_TASKS_API="http://api.local"' in env

    def test_install_includes_webhook_vars_when_set(self, tmp_path, capsys):
        cmd_install(_ns(
            root=str(tmp_path),
            branch="main",
            tasks_api="http://api.local",
            telegram="chat-42",
            slack=None,
            discord=None,
        ))
        env = (tmp_path / LITE_DOT_DIR / "env").read_text()
        assert 'EIGEN_TELEGRAM_CHAT_ID="chat-42"' in env


# ---------------------------------------------------------------------------
# schedule-next
# ---------------------------------------------------------------------------

class TestCmdScheduleNext:
    def test_command_to_skill_mapping(self):
        assert COMMAND_TO_SKILL_LITE == {
            "lite_plan": "eigen-lite:lite_plan",
            "lite_swarm": "eigen-lite:lite_swarm",
            "lite_review": "eigen-lite:lite_review",
        }

    def test_schedule_next_noop_when_pipeline_complete(self, repo, monkeypatch):
        """Plan converged + no epics → noop, exit 0."""
        path = resolve_state_file(repo)
        s = create_initial_state("x")
        s.lite_plan.convergence = LiteConvergence(converged=True)
        save_state(s, path)
        monkeypatch.setenv("CLAUDE_TASKS_API", "http://bogus.local:9999")
        exit_code = cmd_schedule_next(_ns(
            state_file=str(path),
            delay_minutes=1,
            extra_prompt="",
        ))
        assert exit_code == 0
        # Verify the noop was logged
        log_file = repo / LITE_DOT_DIR / "hook_log.jsonl"
        assert log_file.exists()
        entries = [json.loads(line) for line in log_file.read_text().splitlines() if line]
        assert any(e.get("status") == "noop" for e in entries)

    def test_schedule_next_fails_without_api(self, repo_with_state, monkeypatch):
        _, path = repo_with_state
        monkeypatch.delenv("CLAUDE_TASKS_API", raising=False)
        exit_code = cmd_schedule_next(_ns(
            state_file=str(path),
            delay_minutes=1,
            extra_prompt="",
        ))
        assert exit_code == 1

    def test_schedule_next_fails_when_api_unreachable(self, repo_with_state, monkeypatch):
        """Real POST against an unroutable URL — assert we log a failure
        without crashing. This is the closest to an integration test we
        can run without a live claude-tasks service.
        """
        repo_root, path = repo_with_state
        monkeypatch.setenv("CLAUDE_TASKS_API",
                           "http://127.0.0.1:9/bogus")  # port 9 discards
        exit_code = cmd_schedule_next(_ns(
            state_file=str(path),
            delay_minutes=1,
            extra_prompt="",
        ))
        assert exit_code == 1
        log_file = repo_root / LITE_DOT_DIR / "hook_log.jsonl"
        entries = [json.loads(line) for line in log_file.read_text().splitlines() if line]
        assert any(e.get("status") == "failed" for e in entries)
