"""End-to-end tests for eigen-lite-watchdog.sh against the fake API server.

These exercise the shell script itself (subprocess), not Python primitives —
so they catch real issues like flock behavior, env sourcing, and the
Python-in-bash one-liners that format expected task names.

The watchdog expects `eigen-lite` on PATH. A tiny shim script installed
into each test's tmp PATH points at `python -m cli` for the lite repo.
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from cli.models_lite import (
    LiteConvergence,
    LiteEpicState,
    LiteSwarmExecution,
)
from cli.plumbing import LITE_DOT_DIR
from cli.state import create_initial_state, resolve_state_file, save_state

from ._fake_tasks_api import FakeTasksAPI


WATCHDOG_SCRIPT = (
    Path(__file__).resolve().parent.parent / "eigen-lite-watchdog.sh"
)
LITE_ROOT = Path(__file__).resolve().parent.parent.parent  # plugins/eigen-lite


@pytest.fixture
def tasks_api():
    with FakeTasksAPI() as api:
        yield api


@pytest.fixture
def watchdog_env(tmp_path, tasks_api):
    """Full harness: initialized lite repo + env file + eigen-lite shim on PATH."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    state_path = resolve_state_file(project_root)
    s = create_initial_state("wd-test", epic_count=1)
    s.lite_plan.convergence = LiteConvergence(converged=True)
    s.lite_plan.stages_completed = ["A", "B", "C", "D", "E:1"]
    s.epics = {
        "1": LiteEpicState(
            epic_path="phases/phase_1/epic_1/",
            swarm_manifest="phases/phase_1/epic_1/swarm-manifest.json",
            lite_swarm=LiteSwarmExecution(integration_branch="feat/P1.E1"),
        ),
    }
    save_state(s, state_path)

    env_dir = project_root / LITE_DOT_DIR
    env_dir.mkdir()
    (env_dir / "env").write_text(
        f'EIGEN_ROOT="{project_root}"\n'
        f'EIGEN_BRANCH="main"\n'
        f'CLAUDE_TASKS_API="{tasks_api.url}"\n'
    )

    # Install an `eigen-lite` shim on a temporary PATH that delegates to
    # the lite package in this repo (not the installed CLI).
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Use the interpreter running pytest (works in CI with no venv too).
    venv_python = Path(sys.executable)
    shim = bin_dir / "eigen-lite"
    shim.write_text(
        "#!/bin/bash\n"
        f'exec "{venv_python}" -m cli "$@"\n'
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    env_for_shell = os.environ.copy()
    env_for_shell["PATH"] = f"{bin_dir}:{env_for_shell['PATH']}"
    # PYTHONPATH so `python -m cli` resolves to plugins/eigen-lite/cli
    env_for_shell["PYTHONPATH"] = str(LITE_ROOT)

    return project_root, tasks_api, env_for_shell


def _run_watchdog(project_root: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(WATCHDOG_SCRIPT), str(project_root)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestWatchdogHappyPath:
    def test_schedules_next_task_when_pipeline_ready(self, watchdog_env):
        project_root, tasks_api, env = watchdog_env
        result = _run_watchdog(project_root, env)
        assert result.returncode == 0, result.stderr
        assert len(tasks_api.tasks) == 1
        assert tasks_api.tasks[0]["name"] == "eigen-lite: lite_swarm E1"
        assert "SCHEDULED: eigen-lite: lite_swarm E1" in result.stdout

    def test_noop_when_task_already_running(self, watchdog_env):
        project_root, tasks_api, env = watchdog_env
        # Seed an existing running task for this project
        tasks_api.tasks.append({
            "id": 99,
            "name": "eigen-lite: lite_swarm E1",
            "working_dir": str(project_root),
            "last_run_status": "running",
        })
        result = _run_watchdog(project_root, env)
        assert result.returncode == 0
        # No new task posted — still just the seeded one
        assert len(tasks_api.tasks) == 1


class TestWatchdogErrorPaths:
    def test_missing_env_file_errors(self, watchdog_env, tmp_path):
        project_root, _, env = watchdog_env
        (project_root / LITE_DOT_DIR / "env").unlink()
        result = _run_watchdog(project_root, env)
        assert result.returncode == 1
        assert "env file not found" in result.stdout

    def test_missing_project_dir_errors(self, watchdog_env):
        _, _, env = watchdog_env
        result = subprocess.run(
            ["bash", str(WATCHDOG_SCRIPT), "/nonexistent/path"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        assert result.returncode == 1

    def test_api_unreachable_errors(self, watchdog_env):
        project_root, _, env = watchdog_env
        # Replace env file with a bogus API endpoint
        (project_root / LITE_DOT_DIR / "env").write_text(
            f'EIGEN_ROOT="{project_root}"\n'
            f'EIGEN_BRANCH="main"\n'
            'CLAUDE_TASKS_API="http://127.0.0.1:9/bogus"\n'
        )
        result = _run_watchdog(project_root, env)
        assert result.returncode == 1
        assert "unreachable" in result.stdout


class TestWatchdogRetryDetection:
    def test_retry_warning_when_last_task_name_matches(self, watchdog_env):
        project_root, tasks_api, env = watchdog_env
        # Seed a task with the same expected name but non-running
        tasks_api.tasks.append({
            "id": 1,
            "name": "eigen-lite: lite_swarm E1",
            "working_dir": str(project_root),
            "last_run_status": "failed",
        })
        result = _run_watchdog(project_root, env)
        assert result.returncode == 0
        assert "retry detected" in result.stdout
        assert "(RE-RUN)" in result.stdout
        # New task should have been posted with the WARNING extra prompt
        new_task = tasks_api.tasks[-1]
        assert "This is a RE-RUN" in new_task["prompt"]


class TestWatchdogLocking:
    def test_second_concurrent_invocation_exits_cleanly(self, watchdog_env):
        """flock -n means a second run while the first holds the lock
        should exit 0 without attempting any work. Simulate by holding
        the lock from Python.
        """
        import fcntl

        project_root, tasks_api, env = watchdog_env
        lock_path = project_root / LITE_DOT_DIR / "watchdog.lock"
        lock_path.parent.mkdir(exist_ok=True)
        lock_path.touch()
        with open(lock_path, "w") as lockfile:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = _run_watchdog(project_root, env)
            # Another process (us) holds the lock; watchdog must exit 0 silently.
            assert result.returncode == 0
            assert tasks_api.tasks == []
