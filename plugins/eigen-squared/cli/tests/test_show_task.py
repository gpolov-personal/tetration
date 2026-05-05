"""Tests for the ``show-task`` subcommand handler.

D7 contract: the task_name show-task previews must match the task_name
that schedule_command would actually POST. Pre-fix: show-task baked
``f"eigen: {command} (show-task)"`` while production used
``_format_task_name(command, context)`` with three different formats
(initiative / phase / epic). Operators chasing a stuck task by name
were comparing apples to oranges.
"""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

from cli.scheduler import _format_task_name
from cli.subcommands import cmd_show_task


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """Minimal eigen-root with empty .eigen/ so resolve_profile doesn't crash."""
    root = tmp_path / "init"
    (root / ".eigen").mkdir(parents=True)
    monkeypatch.setenv("EIGEN_ROOT", str(root))
    return root


def _run(args: Namespace, capsys) -> dict:
    rc = cmd_show_task(args)
    assert rc == 0, capsys.readouterr().err
    out = capsys.readouterr().out
    return json.loads(out)


def test_show_task_initiative_scope_matches_format_task_name(fake_root, capsys):
    args = Namespace(
        target_command="time_split",
        initiative=str(fake_root),
        phase=None, epic=None,
        extra_prompt="",
        as_json=True,
    )
    body = _run(args, capsys)

    expected = _format_task_name("time_split", {"scope": "initiative", "phase": None, "epic": None})
    assert body["payload"]["name"] == expected
    # Sanity: the literal format we expect for initiative scope.
    assert expected == "eigen: time_split"


def test_show_task_phase_scope_matches_format_task_name(fake_root, capsys):
    args = Namespace(
        target_command="orchestrate_swarm",
        initiative=str(fake_root),
        phase=2, epic=None,
        extra_prompt="",
        as_json=True,
    )
    body = _run(args, capsys)

    expected = _format_task_name(
        "orchestrate_swarm", {"scope": "phase", "phase": 2, "epic": None},
    )
    assert body["payload"]["name"] == expected
    assert expected == "eigen: orchestrate_swarm P2"


def test_show_task_epic_scope_matches_format_task_name(fake_root, capsys):
    args = Namespace(
        target_command="orchestrate_swarm",
        initiative=str(fake_root),
        phase=2, epic=5,
        extra_prompt="",
        as_json=True,
    )
    body = _run(args, capsys)

    expected = _format_task_name(
        "orchestrate_swarm", {"scope": "epic", "phase": 2, "epic": 5},
    )
    assert body["payload"]["name"] == expected
    assert expected == "eigen: orchestrate_swarm P2.E5"


def test_show_task_epic_without_phase_rejected(fake_root, capsys):
    """--epic alone is meaningless (epics are scoped within phases)."""
    args = Namespace(
        target_command="orchestrate_swarm",
        initiative=str(fake_root),
        phase=None, epic=5,
        extra_prompt="",
        as_json=True,
    )
    rc = cmd_show_task(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "epic requires --phase" in err.lower()
