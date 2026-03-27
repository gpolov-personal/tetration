"""Typed data models for pipeline_state.json.

These dataclasses enforce the schema that was previously documented only in
prose in skills/pipeline-state-schema/SKILL.md. Every field has a typed
default, so missing keys in JSON are filled automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

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
    def from_dict(cls, d: dict | None) -> Convergence:
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
    def from_dict(cls, d: dict | None) -> FindingsSummary:
        if not d:
            return cls()
        return cls(
            high=int(d.get("high", 0)),
            medium=int(d.get("medium", 0)),
            low=int(d.get("low", 0)),
        )


@dataclass
class PhaseReview:
    status: str = "not_started"  # not_started | testing | approved
    summary_presented_at: Optional[str] = None
    approved_at: Optional[str] = None
    testing_recipe: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary_presented_at": self.summary_presented_at,
            "approved_at": self.approved_at,
            "testing_recipe": self.testing_recipe,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> PhaseReview:
        if not d:
            return cls()
        return cls(
            status=d.get("status", "not_started"),
            summary_presented_at=d.get("summary_presented_at"),
            approved_at=d.get("approved_at"),
            testing_recipe=d.get("testing_recipe"),
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
    def from_dict(cls, d: dict | None) -> Recommendation:
        if not d:
            return cls()
        return cls(
            from_cmd=d.get("from", ""),
            at_iteration=int(d.get("at_iteration", 0)),
            phase=d.get("phase"),
            epic=d.get("epic"),
            text=d.get("text", ""),
        )


# ---------------------------------------------------------------------------
# Command-level state
# ---------------------------------------------------------------------------

@dataclass
class MainCommandState:
    """State for a main command (time_split, bootstrap, space_split, plan_epic_converge)."""

    status: str = "not_started"  # not_started | completed | iterating
    iteration: int = 0
    last_run_at: Optional[str] = None
    output_paths: dict = field(default_factory=dict)
    feedback_consumed: bool = False
    convergence: Convergence = field(default_factory=Convergence)
    # time_split only:
    phase_count: Optional[int] = None
    # converge commands only (plan_epic_converge):
    findings_summary: Optional[FindingsSummary] = None

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
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> MainCommandState:
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
        )


@dataclass
class DeepenCommandState:
    """State for a deepen command (deepen_time_split, deepen_bootstrap, etc.)."""

    status: str = "not_started"  # not_started | completed
    iteration: int = 0
    last_run_at: Optional[str] = None
    feedback_path: Optional[str] = None
    feedback_consumed: bool = False
    findings_summary: FindingsSummary = field(default_factory=FindingsSummary)
    locked_skills: Optional[list[str]] = None  # Skills locked after first iteration

    def to_dict(self) -> dict:
        d = {
            "status": self.status,
            "iteration": self.iteration,
            "last_run_at": self.last_run_at,
            "feedback_path": self.feedback_path,
            "feedback_consumed": self.feedback_consumed,
            "findings_summary": self.findings_summary.to_dict(),
        }
        if self.locked_skills is not None:
            d["locked_skills"] = self.locked_skills
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> DeepenCommandState:
        if not d:
            return cls()
        return cls(
            status=d.get("status", "not_started"),
            iteration=int(d.get("iteration", 0)),
            last_run_at=d.get("last_run_at"),
            feedback_path=d.get("feedback_path"),
            feedback_consumed=bool(d.get("feedback_consumed", False)),
            findings_summary=FindingsSummary.from_dict(d.get("findings_summary")),
            locked_skills=d.get("locked_skills"),
        )


@dataclass
class SwarmExecution:
    """State for the orchestrate_swarm / review_swarm_pr cycle."""

    status: str = "not_started"  # not_started | pr_created | iterating | converged
    integration_branch: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    manifest_path: Optional[str] = None
    completed_at: Optional[str] = None
    review_iteration: int = 0
    convergence: Convergence = field(default_factory=Convergence)
    findings_summary: dict = field(
        default_factory=lambda: {"p1": 0, "p2": 0, "p3": 0}
    )
    review_reports: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "integration_branch": self.integration_branch,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "manifest_path": self.manifest_path,
            "completed_at": self.completed_at,
            "review_iteration": self.review_iteration,
            "convergence": self.convergence.to_dict(),
            "findings_summary": self.findings_summary,
            "review_reports": self.review_reports,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> SwarmExecution:
        if not d:
            return cls()
        pr_number = d.get("pr_number")
        if pr_number is not None:
            try:
                pr_number = int(pr_number)
            except (ValueError, TypeError):
                pr_number = None
        return cls(
            status=d.get("status", "not_started"),
            integration_branch=d.get("integration_branch"),
            pr_url=d.get("pr_url"),
            pr_number=pr_number,
            manifest_path=d.get("manifest_path"),
            completed_at=d.get("completed_at"),
            review_iteration=int(d.get("review_iteration", 0)),
            convergence=Convergence.from_dict(d.get("convergence")),
            findings_summary=d.get("findings_summary") or {"p1": 0, "p2": 0, "p3": 0},
            review_reports=list(d.get("review_reports") or []),
        )


# ---------------------------------------------------------------------------
# Epic plan (per-epic container)
# ---------------------------------------------------------------------------

@dataclass
class EpicPlan:
    plan_epic_converge: MainCommandState = field(default_factory=MainCommandState)
    swarm_execution: SwarmExecution = field(default_factory=SwarmExecution)

    def to_dict(self) -> dict:
        return {
            "plan_epic_converge": self.plan_epic_converge.to_dict(),
            "swarm_execution": self.swarm_execution.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> EpicPlan:
        if not d:
            return cls()
        return cls(
            plan_epic_converge=MainCommandState.from_dict(d.get("plan_epic_converge")),
            swarm_execution=SwarmExecution.from_dict(d.get("swarm_execution")),
        )


# ---------------------------------------------------------------------------
# Phase state (per-phase container)
# ---------------------------------------------------------------------------

@dataclass
class PhaseState:
    bootstrap: MainCommandState = field(default_factory=MainCommandState)
    deepen_bootstrap: DeepenCommandState = field(default_factory=DeepenCommandState)
    space_split: MainCommandState = field(default_factory=MainCommandState)
    deepen_space_split: DeepenCommandState = field(default_factory=DeepenCommandState)
    phase_review: PhaseReview = field(default_factory=PhaseReview)
    plans: dict[str, EpicPlan] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "bootstrap": self.bootstrap.to_dict(),
            "deepen_bootstrap": self.deepen_bootstrap.to_dict(),
            "space_split": self.space_split.to_dict(),
            "deepen_space_split": self.deepen_space_split.to_dict(),
            "phase_review": self.phase_review.to_dict(),
            "plans": {k: v.to_dict() for k, v in self.plans.items()},
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> PhaseState:
        if not d:
            return cls()
        plans_raw = d.get("plans") or {}
        plans = {k: EpicPlan.from_dict(v) for k, v in plans_raw.items()}
        return cls(
            bootstrap=MainCommandState.from_dict(d.get("bootstrap")),
            deepen_bootstrap=DeepenCommandState.from_dict(d.get("deepen_bootstrap")),
            space_split=MainCommandState.from_dict(d.get("space_split")),
            deepen_space_split=DeepenCommandState.from_dict(
                d.get("deepen_space_split")
            ),
            phase_review=PhaseReview.from_dict(d.get("phase_review")),
            plans=plans,
        )


# ---------------------------------------------------------------------------
# Root state
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    """Root model for pipeline_state.json."""

    schema_version: str = "2.0.0"
    initiative: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    time_split: MainCommandState = field(default_factory=MainCommandState)
    deepen_time_split: DeepenCommandState = field(default_factory=DeepenCommandState)
    phases: dict[str, PhaseState] = field(default_factory=dict)
    recommendations: dict[str, list] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "initiative": self.initiative,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": {
                "time_split": self.time_split.to_dict(),
                "deepen_time_split": self.deepen_time_split.to_dict(),
                "phases": {k: v.to_dict() for k, v in self.phases.items()},
            },
            "recommendations": {
                k: [r.to_dict() if isinstance(r, Recommendation) else r for r in v]
                for k, v in self.recommendations.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> PipelineState:
        if not d:
            return cls()
        state = d.get("state") or {}
        phases_raw = state.get("phases") or {}
        phases = {k: PhaseState.from_dict(v) for k, v in phases_raw.items()}

        recs_raw = d.get("recommendations") or {}
        recommendations: dict[str, list] = {}
        for k, v in recs_raw.items():
            if isinstance(v, list):
                recommendations[k] = [
                    Recommendation.from_dict(r) if isinstance(r, dict) else r
                    for r in v
                ]
            else:
                recommendations[k] = []

        return cls(
            schema_version=d.get("schema_version", "1.0.0"),
            initiative=d.get("initiative", ""),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
            time_split=MainCommandState.from_dict(state.get("time_split")),
            deepen_time_split=DeepenCommandState.from_dict(
                state.get("deepen_time_split")
            ),
            phases=phases,
            recommendations=recommendations,
        )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MAIN_STATUSES = {"not_started", "completed", "iterating"}
VALID_DEEPEN_STATUSES = {"not_started", "completed"}
VALID_SWARM_STATUSES = {"not_started", "pr_created", "iterating", "converged"}
VALID_PHASE_REVIEW_STATUSES = {"not_started", "testing", "approved"}

RECOMMENDATION_MATRIX: dict[str, set[str]] = {
    "deepen_time_split": {"bootstrap", "space_split", "plan_epic_converge", "create_issues_from_plan_swarm"},
    "deepen_bootstrap": {"space_split", "plan_epic_converge", "create_issues_from_plan_swarm"},
    "deepen_space_split": {"plan_epic_converge", "create_issues_from_plan_swarm"},
    "plan_epic_converge": {"create_issues_from_plan_swarm"},
}

MAX_RECOMMENDATIONS_PER_PAIR = 5

DEFAULT_RECOMMENDATIONS = {
    "bootstrap": [],
    "space_split": [],
    "plan_epic_converge": [],
    "create_issues_from_plan_swarm": [],
}
