"""Schema primitives shared by every consumer pipeline state.

These dataclasses are stable building blocks — consumer plugins compose
them into their own schema-specific containers (PhaseState, EpicPlan,
LiteEpicState, etc.). Each primitive owns its serialization round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Convergence:
    converged: bool = False
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "converged": self.converged,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Convergence":
        if not d:
            return cls()
        return cls(
            converged=bool(d.get("converged", False)),
            decided_by=d.get("decided_by"),
            decided_at=d.get("decided_at"),
            reason=d.get("reason"),
        )


@dataclass
class FindingsSummary:
    high: int = 0
    medium: int = 0
    low: int = 0

    def to_dict(self) -> dict:
        return {"high": self.high, "medium": self.medium, "low": self.low}

    @classmethod
    def from_dict(cls, d: dict | None) -> "FindingsSummary":
        if not d:
            return cls()
        return cls(
            high=int(d.get("high", 0)),
            medium=int(d.get("medium", 0)),
            low=int(d.get("low", 0)),
        )


@dataclass
class Recommendation:
    from_cmd: str = ""
    at_iteration: int = 0
    phase: Optional[int] = None
    epic: Optional[int] = None
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "from": self.from_cmd,
            "at_iteration": self.at_iteration,
            "phase": self.phase,
            "epic": self.epic,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Recommendation":
        if not d:
            return cls()
        return cls(
            from_cmd=d.get("from", ""),
            at_iteration=int(d.get("at_iteration", 0)),
            phase=d.get("phase"),
            epic=d.get("epic"),
            text=d.get("text", ""),
        )


@dataclass
class MainCommandState:
    """State for a self-converging main command.

    Used by eigen-squared (time_split, bootstrap_converge, space_split_converge,
    plan_epic_converge) and by eigen-lite (lite_plan). Optional fields like
    `phase_count`, `findings_summary`, `locked_skills` are command-dependent
    and serialized only when set.
    """

    status: str = "not_started"
    iteration: int = 0
    last_run_at: Optional[str] = None
    output_paths: dict = field(default_factory=dict)
    feedback_consumed: bool = False
    convergence: Convergence = field(default_factory=Convergence)
    phase_count: Optional[int] = None
    findings_summary: Optional[FindingsSummary] = None
    locked_skills: Optional[list[str]] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "status": self.status,
            "iteration": self.iteration,
            "last_run_at": self.last_run_at,
            "output_paths": self.output_paths,
            "feedback_consumed": self.feedback_consumed,
            "convergence": self.convergence.to_dict(),
        }
        if self.phase_count is not None:
            d["phase_count"] = self.phase_count
        if self.findings_summary is not None:
            d["findings_summary"] = self.findings_summary.to_dict()
        if self.locked_skills is not None:
            d["locked_skills"] = self.locked_skills
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "MainCommandState":
        if not d:
            return cls()
        phase_count_raw = d.get("phase_count")
        phase_count = None
        if phase_count_raw is not None:
            try:
                phase_count = int(phase_count_raw)
            except (ValueError, TypeError):
                pass
        findings_raw = d.get("findings_summary")
        findings_summary = FindingsSummary.from_dict(findings_raw) if findings_raw else None
        return cls(
            status=d.get("status", "not_started"),
            iteration=int(d.get("iteration", 0)),
            last_run_at=d.get("last_run_at"),
            output_paths=d.get("output_paths") or {},
            feedback_consumed=bool(d.get("feedback_consumed", False)),
            convergence=Convergence.from_dict(d.get("convergence")),
            phase_count=phase_count,
            findings_summary=findings_summary,
            locked_skills=d.get("locked_skills"),
        )
