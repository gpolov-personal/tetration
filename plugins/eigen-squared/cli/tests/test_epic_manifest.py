"""Tests for epic_manifest.py — sequential epic ordering."""

import json
import pytest

from cli.epic_manifest import load_epic_order


@pytest.fixture
def phase_dir(tmp_path):
    """Create a phase directory structure."""
    eigen_root = tmp_path / "project"
    phase_path = eigen_root / "eigen_initiative" / "phases" / "phase_1"
    phase_path.mkdir(parents=True)
    return eigen_root, phase_path


class TestLoadEpicOrder:

    def test_parses_standard_format(self, phase_dir):
        eigen_root, phase_path = phase_dir
        manifest = {
            "execution_order": ["P1.E1", "P1.E2", "P1.E3"],
        }
        (phase_path / "epic_manifest.json").write_text(json.dumps(manifest))
        assert load_epic_order(1, str(eigen_root)) == [1, 2, 3]

    def test_preserves_order(self, phase_dir):
        eigen_root, phase_path = phase_dir
        manifest = {
            "execution_order": ["P1.E3", "P1.E1", "P1.E2"],
        }
        (phase_path / "epic_manifest.json").write_text(json.dumps(manifest))
        assert load_epic_order(1, str(eigen_root)) == [3, 1, 2]

    def test_empty_when_file_missing(self, phase_dir):
        eigen_root, _ = phase_dir
        assert load_epic_order(1, str(eigen_root)) == []

    def test_empty_when_eigen_root_empty(self):
        assert load_epic_order(1, "") == []

    def test_empty_when_execution_order_missing(self, phase_dir):
        eigen_root, phase_path = phase_dir
        manifest = {"epics": [{"id": "P1.E1"}]}
        (phase_path / "epic_manifest.json").write_text(json.dumps(manifest))
        assert load_epic_order(1, str(eigen_root)) == []

    def test_empty_on_empty_execution_order(self, phase_dir):
        eigen_root, phase_path = phase_dir
        manifest = {"execution_order": []}
        (phase_path / "epic_manifest.json").write_text(json.dumps(manifest))
        assert load_epic_order(1, str(eigen_root)) == []

    def test_skips_malformed_epic_ids(self, phase_dir):
        eigen_root, phase_path = phase_dir
        manifest = {
            "execution_order": ["P1.E1", "bad", "P1.Eabc", "P1.E3", ""],
        }
        (phase_path / "epic_manifest.json").write_text(json.dumps(manifest))
        assert load_epic_order(1, str(eigen_root)) == [1, 3]

    def test_handles_invalid_json(self, phase_dir):
        eigen_root, phase_path = phase_dir
        (phase_path / "epic_manifest.json").write_text("not json")
        assert load_epic_order(1, str(eigen_root)) == []

    def test_phase_2(self, phase_dir):
        eigen_root, _ = phase_dir
        phase2 = eigen_root / "eigen_initiative" / "phases" / "phase_2"
        phase2.mkdir(parents=True)
        manifest = {"execution_order": ["P2.E1", "P2.E2"]}
        (phase2 / "epic_manifest.json").write_text(json.dumps(manifest))
        assert load_epic_order(2, str(eigen_root)) == [1, 2]
