"""End-to-end pipeline flow test — real git repo, real subprocess CLI.

Drives the whole state machine the way ``lite_swarm.md`` and ``lite_review.md``
would at runtime: via ``python -m cli <subcommand>`` invocations against a
real git working tree. No mocks.

The swarm itself cannot be spawned from a test (it needs Claude Code agent
teams), so we hand-craft the artifacts a swarm *would* produce
(`swarm-manifest.json`, a code commit on ``feat/P1.E<M>``, a review report)
and verify the CLI glue advances correctly at every step.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from cli.state import resolve_state_file


LITE_ROOT = Path(__file__).resolve().parent.parent.parent  # plugins/eigen-lite
VENV_PY = (
    LITE_ROOT.parent / "eigen-squared" / ".venv" / "bin" / "python"
)


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


def _cli(args, cwd, env, capture=True) -> subprocess.CompletedProcess:
    """Invoke ``python -m cli <args>`` with PYTHONPATH pinned to the lite repo."""
    return subprocess.run(
        [str(VENV_PY), "-m", "cli", *args],
        cwd=cwd,
        env=env,
        capture_output=capture,
        text=True,
        timeout=30,
    )


@pytest.fixture
def repo(tmp_path):
    _git(["init", "-q", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    (tmp_path / "README.md").write_text("# seed\n")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    return tmp_path


@pytest.fixture
def env(repo):
    e = os.environ.copy()
    e["EIGEN_ROOT"] = str(repo)
    e["EIGEN_BRANCH"] = "main"
    e["PYTHONPATH"] = str(LITE_ROOT)
    return e


class TestFullPipelineFlow:
    """Walk a 2-epic initiative from init through E1+E2 convergence."""

    def test_end_to_end_flow(self, repo, env):
        # ── 1. init ────────────────────────────────────────────────────────
        r = _cli(["init", "--feature-set", "demo", "--epic-count", "2"],
                 cwd=repo, env=env)
        assert r.returncode == 0, r.stderr
        assert resolve_state_file(repo).exists()

        # ── 2. init-epics (2 feature epics, no e2e) ────────────────────────
        epics_json = json.dumps([
            {"epic": 1, "is_e2e_epic": False},
            {"epic": 2, "is_e2e_epic": False},
        ])
        r = _cli(["init-epics", "--epics", epics_json], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        # ── 3. next → lite_plan (nothing converged yet) ─────────────────────
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["command"] == "lite_plan"
        assert nxt["context"]["scope"] == "initiative"

        # ── 4. simulate lite_plan stages A..E:<n> then converge ────────────
        for stage in ["A", "B", "C", "D", "E:1", "E:2"]:
            _cli(["complete", "lite_plan", "--stage", stage],
                 cwd=repo, env=env)
        r = _cli(
            ["mark-converged", "lite_plan", "--reason", "plan complete"],
            cwd=repo, env=env,
        )
        assert r.returncode == 0, r.stderr

        # ── 5. next → lite_swarm E1 ─────────────────────────────────────────
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["command"] == "lite_swarm"
        assert nxt["context"]["epic"] == 1
        assert nxt["context"]["scope"] == "epic"

        # ── 6. get-context lite_swarm --epic 1 (shape contract) ─────────────
        r = _cli(["get-context", "lite_swarm", "--epic", "1", "--json"],
                 cwd=repo, env=env)
        assert r.returncode == 0, r.stderr
        ctx = json.loads(r.stdout)
        # Fields consumed by lite_swarm.md "On Entry":
        for key in ("command", "scope", "epic", "branch", "manifest_path",
                    "epic_path", "is_e2e_epic", "swarm_status",
                    "review_iteration", "pr_number", "pr_url"):
            assert key in ctx, f"missing {key} in lite_swarm context"
        assert ctx["branch"] == "feat/P1.E1"
        assert ctx["swarm_status"] == "not_started"
        assert ctx["review_iteration"] == 0
        assert ctx["pr_number"] is None

        # ── 7. checkout integration branch ──────────────────────────────────
        r = _cli(["checkout-branch", "--epic", "1", "--create"],
                 cwd=repo, env=env)
        assert r.returncode == 0, r.stderr
        head = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, capture_output=True, text=True,
        ).stdout.strip()
        assert head == "feat/P1.E1"

        # ── 8. Simulate what the swarm would do: write manifest + code ─────
        epic1_dir = repo / "eigen_initiative" / "phases" / "phase_1" / "epic_1"
        epic1_dir.mkdir(parents=True)
        manifest = {
            "epic_id": "P1.E1",
            "tasks": [{
                "id": "P1.E1.T001",
                "summary": "seed feature",
                "files_owned": ["src/feature.py"],
                "test_files_owned": ["tests/test_feature.py"],
                "blocked_by": [],
                "model": "opus",
            }],
            "execution_waves": [["P1.E1.T001"]],
            "shared_files": [],
        }
        (epic1_dir / "swarm-manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
        (repo / "src").mkdir()
        (repo / "src" / "feature.py").write_text("def feature(): return 1\n")
        _git(["add", "."], repo)
        _git(["commit", "-q", "-m", "feat(P1.E1): seed feature"], repo)

        # ── 9. complete lite_swarm --epic 1 --pr-number 42 ─────────────────
        r = _cli([
            "complete", "lite_swarm", "--epic", "1",
            "--pr-number", "42",
            "--pr-url", "https://example/pr/42",
        ], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        # ── 10. next → lite_review E1 (swarm is now pr_created) ────────────
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["command"] == "lite_review"
        assert nxt["context"]["epic"] == 1

        # ── 11. get-context lite_review --epic 1 (PR visible) ──────────────
        r = _cli(["get-context", "lite_review", "--epic", "1", "--json"],
                 cwd=repo, env=env)
        ctx = json.loads(r.stdout)
        assert ctx["pr_number"] == 42
        assert ctx["pr_url"] == "https://example/pr/42"
        assert ctx["swarm_status"] == "pr_created"
        assert ctx["review_iteration"] == 0

        # ── 12. Simulate review report ─────────────────────────────────────
        report = epic1_dir / "review_report_iteration_0.md"
        report.write_text("# Review 0\nConverged — zero findings.\n")
        r = _cli([
            "complete", "lite_review", "--epic", "1",
            "--report-path", str(report.relative_to(repo)),
            "--findings-summary", '{"p1": 0, "p2": 0, "p3": 0}',
        ], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        # ── 13. mark lite_swarm converged for E1 ────────────────────────────
        r = _cli([
            "mark-converged", "lite_swarm", "--epic", "1",
            "--reason", "All findings resolved.",
        ], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        # ── 14. next → lite_swarm E2 (epic 1 is done) ──────────────────────
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["command"] == "lite_swarm"
        assert nxt["context"]["epic"] == 2
        assert nxt["context"]["branch"] == "feat/P1.E2"

        # ── 15. Walk E2 through to convergence, then pipeline complete ─────
        r = _cli([
            "complete", "lite_swarm", "--epic", "2",
            "--pr-number", "43",
        ], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        r = _cli([
            "complete", "lite_review", "--epic", "2",
            "--report-path", "phases/phase_1/epic_2/review_report_iteration_0.md",
            "--findings-summary", '{"p1": 0, "p2": 0, "p3": 1}',
        ], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        r = _cli([
            "mark-converged", "lite_swarm", "--epic", "2",
            "--reason", "1 residual P3 recorded.",
        ], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        # ── 16. next → complete (nothing left) ──────────────────────────────
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["status"] == "complete"
        assert nxt["command"] is None

        # ── 17. validate — state is well-formed at the end ─────────────────
        r = _cli(["validate"], cwd=repo, env=env)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["valid"] is True


class TestLitePlanStageProgression:
    """Walk the lite_plan stage markers A → B → C → D → E:<M> end-to-end via
    the CLI. lite_plan.md consumes get-context fields (stages_completed,
    output_paths, iteration) — this test pins the shape contract.
    """

    def test_stages_advance_and_get_context_exposes_them(self, repo, env):
        _cli(["init", "--feature-set", "planner", "--epic-count", "2"],
             cwd=repo, env=env)

        # Initial get-context: no stages completed yet.
        r = _cli(["get-context", "lite_plan", "--json"], cwd=repo, env=env)
        ctx = json.loads(r.stdout)
        assert ctx["command"] == "lite_plan"
        assert ctx["scope"] == "initiative"
        assert ctx["stages_completed"] == []
        # Default output_paths has the schema's optional slots pre-filled with
        # None; what matters is that they're unset (falsy) at start.
        assert all(v is None for v in ctx["output_paths"].values())
        assert ctx["iteration"] == 0

        # Stage A: record the feature_summary path.
        _cli([
            "complete", "lite_plan", "--stage", "A",
            "--output-paths",
            '{"feature_summary": "eigen_initiative/feature_summary.md"}',
        ], cwd=repo, env=env)

        # Stage B, C advance the same way.
        _cli(["complete", "lite_plan", "--stage", "B"], cwd=repo, env=env)
        _cli(["complete", "lite_plan", "--stage", "C"], cwd=repo, env=env)

        # Stage D creates epic manifest + init-epics CLI call.
        _cli(["complete", "lite_plan", "--stage", "D"], cwd=repo, env=env)
        _cli(["init-epics", "--epics",
              json.dumps([
                  {"epic": 1, "is_e2e_epic": False},
                  {"epic": 2, "is_e2e_epic": True},
              ])],
             cwd=repo, env=env)

        # Stage E:1 and E:2 per-epic markers.
        _cli(["complete", "lite_plan", "--stage", "E:1"], cwd=repo, env=env)
        _cli(["complete", "lite_plan", "--stage", "E:2"], cwd=repo, env=env)

        # Final get-context: lite_plan.md's On-Entry sees all markers and
        # resumes by skipping every stage.
        r = _cli(["get-context", "lite_plan", "--json"], cwd=repo, env=env)
        ctx = json.loads(r.stdout)
        assert ctx["stages_completed"] == ["A", "B", "C", "D", "E:1", "E:2"]
        assert ctx["output_paths"]["feature_summary"] == (
            "eigen_initiative/feature_summary.md"
        )
        assert ctx["iteration"] >= 1  # incremented by each complete call

        # Converge lite_plan → next advances to lite_swarm E1.
        _cli(["mark-converged", "lite_plan",
              "--reason", "all stages complete"], cwd=repo, env=env)
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["command"] == "lite_swarm"
        assert nxt["context"]["epic"] == 1


class TestFixupIterationFlow:
    """After lite_review finds issues, pipeline goes back to lite_swarm."""

    def test_non_converged_review_sends_swarm_back_to_iterating(self, repo, env):
        _cli(["init", "--feature-set", "x", "--epic-count", "1"],
             cwd=repo, env=env)
        _cli(["init-epics", "--epics",
              json.dumps([{"epic": 1, "is_e2e_epic": False}])],
             cwd=repo, env=env)
        _cli(["mark-converged", "lite_plan", "--reason", "done"],
             cwd=repo, env=env)
        _cli(["complete", "lite_swarm", "--epic", "1", "--pr-number", "10"],
             cwd=repo, env=env)

        # Review finds P1 issues — CLI advances to "iterating"
        _cli([
            "complete", "lite_review", "--epic", "1",
            "--report-path", "phases/phase_1/epic_1/review_report_iteration_0.md",
            "--findings-summary", '{"p1": 2, "p2": 1, "p3": 0}',
        ], cwd=repo, env=env)
        r = _cli(["set-swarm-status", "iterating", "--epic", "1"],
                 cwd=repo, env=env)
        assert r.returncode == 0, r.stderr

        # next should still point back at lite_swarm E1 for fixup execution
        r = _cli(["next", "--json"], cwd=repo, env=env)
        nxt = json.loads(r.stdout)
        assert nxt["command"] == "lite_swarm"
        assert nxt["context"]["epic"] == 1

        # get-context must reflect iterating status so the command knows
        # to behave as a fixup run (see lite_swarm.md "On Entry").
        r = _cli(["get-context", "lite_swarm", "--epic", "1", "--json"],
                 cwd=repo, env=env)
        ctx = json.loads(r.stdout)
        assert ctx["swarm_status"] == "iterating"
        assert ctx["pr_number"] == 10
        assert ctx["review_iteration"] == 1  # one completed review
