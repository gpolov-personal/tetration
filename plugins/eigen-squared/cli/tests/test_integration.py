"""Integration test: simulate a full pipeline walk via CLI subcommands.

This test walks through the entire pipeline lifecycle:
  init → complete time_split → complete deepen_time_split → mark-converged →
  complete bootstrap → complete deepen_bootstrap → mark-converged →
  complete space_split → ... → all phases approved
"""

import json
import os
import pytest
from pathlib import Path

from cli.main import main as cli_main


@pytest.fixture
def pipeline_env(tmp_path):
    """Set up a temporary pipeline environment."""
    eigen_root = tmp_path / "project"
    eigen_root.mkdir()
    phases_dir = eigen_root / "eigen_initiative" / "phases"
    phases_dir.mkdir(parents=True)

    # Create a mock epic_manifest.json for phase 1
    phase_dir = phases_dir / "phase_1"
    phase_dir.mkdir()
    manifest = {
        "phase": 1,
        "epic_count": 1,
        "execution_order": ["P1.E1"],
        "epics": [{"id": "P1.E1", "epic_number": 1, "name": "Test Epic"}],
    }
    (phase_dir / "epic_manifest.json").write_text(json.dumps(manifest))

    old_root = os.environ.get("EIGEN_ROOT")
    old_branch = os.environ.get("EIGEN_BRANCH")
    os.environ["EIGEN_ROOT"] = str(eigen_root)
    os.environ["EIGEN_BRANCH"] = "main"

    yield eigen_root

    if old_root is not None:
        os.environ["EIGEN_ROOT"] = old_root
    else:
        os.environ.pop("EIGEN_ROOT", None)
    if old_branch is not None:
        os.environ["EIGEN_BRANCH"] = old_branch
    else:
        os.environ.pop("EIGEN_BRANCH", None)


def run(argv: list[str]) -> int:
    """Run a CLI command and return exit code."""
    return cli_main(argv)


def run_json(argv: list[str]) -> dict:
    """Run a CLI command and capture JSON output."""
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        cli_main(argv)
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue().strip()
    return json.loads(output) if output else {}


class TestFullPipelineWalk:

    def test_init_creates_state(self, pipeline_env):
        assert run(["init", "--initiative", "Test", "--phase-count", "1"]) == 0
        sf = pipeline_env / "eigen_initiative" / "phases" / "pipeline_state.json"
        assert sf.exists()
        state = json.loads(sf.read_text())
        assert state["initiative"] == "Test"
        assert "1" in state["state"]["phases"]

    def test_next_after_init_is_time_split(self, pipeline_env):
        run(["init", "--initiative", "Test", "--phase-count", "1"])
        result = run_json(["next", "--json"])
        assert result["command"] == "time_split"

    def test_complete_time_split(self, pipeline_env):
        run(["init", "--initiative", "Test", "--phase-count", "1"])
        run(["complete", "time_split", "--phase-count", "1",
             "--output-path", "phases/summary.json"])
        result = run_json(["next", "--json"])
        assert result["command"] == "deepen_time_split"

    def test_convergence_cycle_to_bootstrap(self, pipeline_env):
        """Full time_split ↔ deepen_time_split cycle ending in convergence."""
        run(["init", "--initiative", "Test", "--phase-count", "1"])

        # time_split completes
        run(["complete", "time_split", "--phase-count", "1",
             "--output-path", "phases/summary.json"])

        # deepen_time_split completes
        run(["complete", "deepen_time_split",
             "--feedback-path", "phases/feedback/dt.json",
             "--findings-summary", '{"high":0,"medium":0,"low":1}'])

        # Converge
        run(["mark-converged", "time_split", "--reason", "Zero high/medium"])

        # Next should be bootstrap
        result = run_json(["next", "--json"])
        assert result["command"] == "bootstrap"
        assert result["context"]["phase"] == 1

    def test_full_phase_walk(self, pipeline_env):
        """Walk through init → time_split → bootstrap → space_split → plan → create_issues."""
        run(["init", "--initiative", "Test", "--phase-count", "1"])

        # time_split cycle
        run(["complete", "time_split", "--phase-count", "1", "--output-path", "x"])
        run(["complete", "deepen_time_split", "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "time_split", "--reason", "clean"])

        # bootstrap cycle
        assert run_json(["next", "--json"])["command"] == "bootstrap"
        run(["complete", "bootstrap", "--phase", "1", "--output-path", "report.json"])
        assert run_json(["next", "--json"])["command"] == "deepen_bootstrap"
        run(["complete", "deepen_bootstrap", "--phase", "1", "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "bootstrap", "--phase", "1", "--reason", "clean"])

        # space_split cycle
        assert run_json(["next", "--json"])["command"] == "space_split"
        run(["complete", "space_split", "--phase", "1", "--epic-manifest", "dag.json", "--e2e-config", "e2e.json"])
        assert run_json(["next", "--json"])["command"] == "deepen_space_split"
        run(["complete", "deepen_space_split", "--phase", "1", "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "space_split", "--phase", "1", "--reason", "clean"])

        # plan_phase_epic
        result = run_json(["next", "--json"])
        assert result["command"] == "plan_phase_epic"
        assert result["context"]["epic"] == 1
        run(["init-plan", "--phase", "1", "--epic", "1"])
        run(["complete", "plan_phase_epic", "--phase", "1", "--epic", "1", "--plan-file", "plan.md"])
        run(["complete", "deepen_plan_phase_epic", "--phase", "1", "--epic", "1", "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "plan_phase_epic", "--phase", "1", "--epic", "1", "--reason", "clean"])

        # create_issues_from_plan_swarm
        assert run_json(["next", "--json"])["command"] == "create_issues_from_plan_swarm"
        run(["complete", "create_issues_from_plan_swarm", "--phase", "1", "--epic", "1",
             "--manifest-path", "manifest.json", "--integration-branch", "feat/P1.E1"])

        # orchestrate_swarm
        assert run_json(["next", "--json"])["command"] == "orchestrate_swarm"
        run(["complete", "orchestrate_swarm", "--phase", "1", "--epic", "1",
             "--pr-url", "https://github.com/test/pull/1", "--pr-number", "1"])

        # review_swarm_pr
        assert run_json(["next", "--json"])["command"] == "review_swarm_pr"
        run(["complete", "review_swarm_pr", "--phase", "1", "--epic", "1",
             "--report-path", "report.md", "--findings-summary", '{"p1":0,"p2":0,"p3":0}'])
        run(["mark-converged", "swarm_execution", "--phase", "1", "--epic", "1",
             "--reason", "No findings"])

        # All epics converged → human checkpoint (None)
        result = run_json(["next", "--json"])
        assert result["command"] is None

    def test_validate_after_walk(self, pipeline_env):
        """State remains valid throughout the pipeline walk."""
        run(["init", "--initiative", "Test", "--phase-count", "1"])
        assert run(["validate"]) == 0

        run(["complete", "time_split", "--phase-count", "1", "--output-path", "x"])
        assert run(["validate"]) == 0

        run(["complete", "deepen_time_split", "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        assert run(["validate"]) == 0

    def test_get_context_returns_correct_info(self, pipeline_env):
        run(["init", "--initiative", "Test", "--phase-count", "1"])
        ctx = run_json(["get-context", "time_split", "--json"])
        assert ctx["command"] == "time_split"
        assert ctx["is_first_run"] is True
        assert ctx["iteration"] == 1

    def test_recommendations(self, pipeline_env):
        run(["init", "--initiative", "Test", "--phase-count", "1"])
        run(["complete", "time_split", "--phase-count", "1", "--output-path", "x"])
        run(["complete", "deepen_time_split", "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "time_split", "--reason", "clean"])

        # Add recommendation
        assert run(["add-recommendation", "--from-cmd", "deepen_time_split",
                     "--target", "bootstrap", "--text", "Check entity stubs"]) == 0

        # Get context should include it
        ctx = run_json(["get-context", "bootstrap", "--phase", "1", "--json"])
        assert len(ctx["recommendations"]) == 1

        # Clear
        run(["clear-recommendations", "--from-cmd", "deepen_time_split"])
        ctx = run_json(["get-context", "bootstrap", "--phase", "1", "--json"])
        assert len(ctx["recommendations"]) == 0

    def test_status_shows_pipeline(self, pipeline_env, capsys):
        run(["init", "--initiative", "Test", "--phase-count", "2"])
        run(["status"])
        captured = capsys.readouterr()
        assert "Test" in captured.out
        assert "Phase 1:" in captured.out
        assert "Phase 2:" in captured.out
        assert "time_split" in captured.out

    def test_multi_phase_2epic_walk(self, pipeline_env):
        """Full 2-phase, 2-epic pipeline walk with phase approval transitions."""
        # Create epic_manifest for phase 2
        phase2_dir = pipeline_env / "eigen_initiative" / "phases" / "phase_2"
        phase2_dir.mkdir(parents=True, exist_ok=True)
        manifest2 = {
            "phase": 2, "epic_count": 1,
            "execution_order": ["P2.E1"],
            "epics": [{"id": "P2.E1", "epic_number": 1}],
        }
        (phase2_dir / "epic_manifest.json").write_text(json.dumps(manifest2))

        run(["init", "--initiative", "Test", "--phase-count", "2"])

        # === TIME_SPLIT (initiative-level, once) ===
        run(["complete", "time_split", "--phase-count", "2", "--output-path", "x"])
        run(["complete", "deepen_time_split", "--feedback-path", "f",
             "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "time_split", "--reason", "clean"])

        # === PHASE 1 ===
        assert run_json(["next", "--json"])["command"] == "bootstrap"
        assert run_json(["next", "--json"])["context"]["phase"] == 1

        # Bootstrap P1
        run(["complete", "bootstrap", "--phase", "1", "--output-path", "r.json"])
        run(["complete", "deepen_bootstrap", "--phase", "1", "--feedback-path", "f",
             "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "bootstrap", "--phase", "1", "--reason", "clean"])

        # Space_split P1
        run(["complete", "space_split", "--phase", "1", "--epic-manifest", "m.json", "--e2e-config", "e.json"])
        run(["complete", "deepen_space_split", "--phase", "1", "--feedback-path", "f",
             "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "space_split", "--phase", "1", "--reason", "clean"])

        # Epic P1.E1
        result = run_json(["next", "--json"])
        assert result["command"] == "plan_phase_epic"
        assert result["context"]["epic"] == 1

        run(["init-plan", "--phase", "1", "--epic", "1"])
        run(["complete", "plan_phase_epic", "--phase", "1", "--epic", "1", "--plan-file", "p.md"])
        run(["complete", "deepen_plan_phase_epic", "--phase", "1", "--epic", "1",
             "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "plan_phase_epic", "--phase", "1", "--epic", "1", "--reason", "clean"])
        run(["complete", "create_issues_from_plan_swarm", "--phase", "1", "--epic", "1",
             "--manifest-path", "m.json", "--integration-branch", "feat/P1.E1"])
        run(["complete", "orchestrate_swarm", "--phase", "1", "--epic", "1",
             "--pr-url", "http://pr/1", "--pr-number", "1"])
        run(["complete", "review_swarm_pr", "--phase", "1", "--epic", "1",
             "--report-path", "r.md", "--findings-summary", '{"p1":0,"p2":0,"p3":0}'])
        run(["mark-converged", "swarm_execution", "--phase", "1", "--epic", "1",
             "--reason", "clean"])

        # All epics P1 converged → human checkpoint
        result = run_json(["next", "--json"])
        assert result["command"] is None, "Should be human checkpoint after all epics converge"

        # Phase review: testing → still None
        run(["set-phase-review", "--phase", "1", "--status", "testing"])
        result = run_json(["next", "--json"])
        assert result["command"] is None, "Should still be None during testing"

        # Phase review: approved → Phase 2 bootstrap
        run(["set-phase-review", "--phase", "1", "--status", "approved"])
        result = run_json(["next", "--json"])
        assert result["command"] == "bootstrap", "Phase 2 should start with bootstrap"
        assert result["context"]["phase"] == 2, "Should be phase 2, not phase 1"

        # === PHASE 2 ===
        # Bootstrap P2
        run(["complete", "bootstrap", "--phase", "2", "--output-path", "r.json"])
        run(["complete", "deepen_bootstrap", "--phase", "2", "--feedback-path", "f",
             "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "bootstrap", "--phase", "2", "--reason", "clean"])

        # Space_split P2
        run(["complete", "space_split", "--phase", "2", "--epic-manifest", "m.json", "--e2e-config", "e.json"])
        run(["complete", "deepen_space_split", "--phase", "2", "--feedback-path", "f",
             "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "space_split", "--phase", "2", "--reason", "clean"])

        # Epic P2.E1
        run(["init-plan", "--phase", "2", "--epic", "1"])
        run(["complete", "plan_phase_epic", "--phase", "2", "--epic", "1", "--plan-file", "p.md"])
        run(["complete", "deepen_plan_phase_epic", "--phase", "2", "--epic", "1",
             "--feedback-path", "f", "--findings-summary", '{"high":0,"medium":0,"low":0}'])
        run(["mark-converged", "plan_phase_epic", "--phase", "2", "--epic", "1", "--reason", "clean"])
        run(["complete", "create_issues_from_plan_swarm", "--phase", "2", "--epic", "1",
             "--manifest-path", "m.json", "--integration-branch", "feat/P2.E1"])
        run(["complete", "orchestrate_swarm", "--phase", "2", "--epic", "1",
             "--pr-url", "http://pr/2", "--pr-number", "2"])
        run(["complete", "review_swarm_pr", "--phase", "2", "--epic", "1",
             "--report-path", "r.md", "--findings-summary", '{"p1":0,"p2":0,"p3":0}'])
        run(["mark-converged", "swarm_execution", "--phase", "2", "--epic", "1",
             "--reason", "clean"])

        # Phase 2 complete → human checkpoint
        result = run_json(["next", "--json"])
        assert result["command"] is None

        # Approve phase 2 → pipeline complete
        run(["set-phase-review", "--phase", "2", "--status", "approved"])
        result = run_json(["next", "--json"])
        assert result["command"] is None, "All phases approved — pipeline complete"
