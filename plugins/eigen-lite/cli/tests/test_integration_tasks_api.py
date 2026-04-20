"""Integration tests against a live HTTP server that implements the
claude-tasks API subset eigen-lite uses. No mocks — the scheduler performs
a real POST via the same curl subprocess it uses in production.
"""

import json
from argparse import Namespace

import pytest

from cli.models_lite import (
    LiteConvergence,
    LiteEpicState,
    LiteSwarmExecution,
)
from cli.plumbing import LITE_DOT_DIR, cmd_schedule_next
from cli.state import create_initial_state, resolve_state_file, save_state

from ._fake_tasks_api import FakeTasksAPI


@pytest.fixture
def tasks_api():
    with FakeTasksAPI() as api:
        yield api


@pytest.fixture
def lite_repo(tmp_path, tasks_api, monkeypatch):
    path = resolve_state_file(tmp_path)
    s = create_initial_state("integ-test", epic_count=1)
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

    monkeypatch.setenv("EIGEN_ROOT", str(tmp_path))
    monkeypatch.setenv("EIGEN_BRANCH", "main")
    monkeypatch.setenv("CLAUDE_TASKS_API", tasks_api.url)
    return tmp_path, path


def _ns(**kwargs) -> Namespace:
    return Namespace(**kwargs)


class TestScheduleNextAgainstRealAPI:
    def test_posts_task_to_api(self, lite_repo, tasks_api):
        _, path = lite_repo
        exit_code = cmd_schedule_next(_ns(
            state_file=str(path),
            delay_minutes=1,
            extra_prompt="",
        ))
        assert exit_code == 0
        assert len(tasks_api.tasks) == 1
        task = tasks_api.tasks[0]
        assert task["name"] == "eigen-lite: lite_swarm E1"
        assert task["enabled"] is True
        assert 'Skill("eigen-lite:lite_swarm")' in task["prompt"]

    def test_dedup_within_window_no_second_post(self, lite_repo, tasks_api):
        _, path = lite_repo
        args = _ns(state_file=str(path), delay_minutes=1, extra_prompt="")
        assert cmd_schedule_next(args) == 0
        # Immediate second call — should deduplicate
        assert cmd_schedule_next(args) == 0
        assert len(tasks_api.tasks) == 1  # still only one POST landed

    def test_hook_log_written_with_confirmed_status(self, lite_repo, tasks_api):
        root, path = lite_repo
        cmd_schedule_next(_ns(state_file=str(path), delay_minutes=1,
                              extra_prompt=""))
        log_file = root / LITE_DOT_DIR / "hook_log.jsonl"
        assert log_file.exists()
        entries = [json.loads(l) for l in log_file.read_text().splitlines() if l]
        confirmed = [e for e in entries if e.get("status") == "confirmed"]
        assert len(confirmed) == 1
        assert confirmed[0]["command"] == "lite_swarm"
        assert confirmed[0]["context_key"] == "epic:E1"

    def test_context_key_initiative_for_lite_plan(self, tmp_path, tasks_api, monkeypatch):
        """When lite_plan hasn't converged, context_key is 'initiative'."""
        path = resolve_state_file(tmp_path)
        save_state(create_initial_state("fresh", epic_count=0), path)
        monkeypatch.setenv("EIGEN_ROOT", str(tmp_path))
        monkeypatch.setenv("EIGEN_BRANCH", "main")
        monkeypatch.setenv("CLAUDE_TASKS_API", tasks_api.url)

        cmd_schedule_next(_ns(state_file=str(path), delay_minutes=1,
                              extra_prompt=""))
        assert tasks_api.tasks[0]["name"] == "eigen-lite: lite_plan"
        log = (tmp_path / LITE_DOT_DIR / "hook_log.jsonl").read_text()
        assert any(json.loads(l).get("context_key") == "initiative"
                   for l in log.splitlines() if l)

    def test_telegram_webhook_forwarded_when_env_set(self, lite_repo, tasks_api, monkeypatch):
        _, path = lite_repo
        monkeypatch.setenv("EIGEN_TELEGRAM_CHAT_ID", "chat-xyz")
        cmd_schedule_next(_ns(state_file=str(path), delay_minutes=1,
                              extra_prompt=""))
        assert tasks_api.tasks[0].get("telegram_webhook") == "chat-xyz"

    def test_extra_prompt_appended(self, lite_repo, tasks_api):
        _, path = lite_repo
        cmd_schedule_next(_ns(
            state_file=str(path), delay_minutes=1,
            extra_prompt="WARNING: re-run detected",
        ))
        assert "WARNING: re-run detected" in tasks_api.tasks[0]["prompt"]

    def test_schedule_records_failure_when_server_returns_error(self, lite_repo, monkeypatch):
        """Point at a bogus port so curl exits non-zero; hook log records failure."""
        root, path = lite_repo
        monkeypatch.setenv("CLAUDE_TASKS_API", "http://127.0.0.1:9/bogus")
        exit_code = cmd_schedule_next(_ns(
            state_file=str(path), delay_minutes=1, extra_prompt="",
        ))
        assert exit_code == 1
        entries = [json.loads(l) for l in (
            root / LITE_DOT_DIR / "hook_log.jsonl"
        ).read_text().splitlines() if l]
        assert any(e.get("status") == "failed" for e in entries)
