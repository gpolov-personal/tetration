"""Round-trip tests for the schema primitives in base_models."""

from eigen_core.cli.base_models import (
    Convergence,
    FindingsSummary,
    MainCommandState,
    Recommendation,
)


class TestConvergence:
    def test_default_round_trip(self):
        c = Convergence()
        assert Convergence.from_dict(c.to_dict()) == c

    def test_populated_round_trip(self):
        c = Convergence(converged=True, decided_by="reviewer", decided_at="t", reason="ok")
        assert Convergence.from_dict(c.to_dict()) == c

    def test_from_none_returns_default(self):
        assert Convergence.from_dict(None) == Convergence()


class TestFindingsSummary:
    def test_default_zero(self):
        f = FindingsSummary()
        assert f.high == 0 and f.medium == 0 and f.low == 0

    def test_round_trip(self):
        f = FindingsSummary(high=2, medium=3, low=1)
        assert FindingsSummary.from_dict(f.to_dict()) == f

    def test_from_none_returns_default(self):
        assert FindingsSummary.from_dict(None) == FindingsSummary()


class TestMainCommandState:
    def test_default_round_trip(self):
        s = MainCommandState()
        round_tripped = MainCommandState.from_dict(s.to_dict())
        assert round_tripped == s

    def test_optional_fields_omitted_when_none(self):
        s = MainCommandState()
        d = s.to_dict()
        assert "phase_count" not in d
        assert "findings_summary" not in d
        assert "locked_skills" not in d

    def test_phase_count_serialized(self):
        s = MainCommandState(phase_count=5)
        assert s.to_dict()["phase_count"] == 5

    def test_findings_summary_round_trip(self):
        s = MainCommandState(findings_summary=FindingsSummary(high=1, medium=2, low=3))
        round_tripped = MainCommandState.from_dict(s.to_dict())
        assert round_tripped.findings_summary == FindingsSummary(high=1, medium=2, low=3)

    def test_phase_count_garbage_becomes_none(self):
        s = MainCommandState.from_dict({"phase_count": "not-a-number"})
        assert s.phase_count is None

    def test_convergence_nested_round_trip(self):
        s = MainCommandState(convergence=Convergence(converged=True, reason="done"))
        round_tripped = MainCommandState.from_dict(s.to_dict())
        assert round_tripped.convergence.converged is True
        assert round_tripped.convergence.reason == "done"


class TestRecommendation:
    def test_round_trip_uses_from_alias(self):
        r = Recommendation(from_cmd="bootstrap_converge", at_iteration=2,
                           phase=1, epic=3, text="check this")
        d = r.to_dict()
        assert d["from"] == "bootstrap_converge"
        assert Recommendation.from_dict(d) == r
