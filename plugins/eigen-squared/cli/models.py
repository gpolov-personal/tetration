"""Typed data models for pipeline_state.json.

These dataclasses are the single source of truth for the pipeline state schema.
Every field has a typed default, so missing keys in JSON are filled automatically.
Commands MUST use the CLI to read/write pipeline state — never manipulate the JSON directly.

Primitives shared with eigen-lite live in ``eigen_core.cli.base_models`` and
are re-exported below to preserve the ``cli.models`` import path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from eigen_core.cli.base_models import (
    Convergence,
    FindingsSummary,
    MainCommandState,
    Recommendation,
)


@dataclass
class PhaseReview:
    status: str = "not_started"  # not_started | testing | approved
    summary_presented_at: Optional[str] = None
    approved_at: Optional[str] = None
    testing_recipe: Optional[str] = None
    # Set to True only when the user typed APPROVE-DEGRADED on the
    # eigen_continue Mode 2 prompt for a phase containing degraded epics
    # (CAPPED_BY_OSCILLATION, P1_REGRESSION_PERSISTENT, DIVERGING_LOOP,
    # SWEEP_ABORTED, CAP_REACHED_WITH_RESIDUAL). The watchdog refuses to
    # auto-launch Phase N+1 when any epic is degraded and this flag is
    # not also True.
    degraded_acknowledged: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary_presented_at": self.summary_presented_at,
            "approved_at": self.approved_at,
            "testing_recipe": self.testing_recipe,
            "degraded_acknowledged": self.degraded_acknowledged,
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
            degraded_acknowledged=bool(d.get("degraded_acknowledged", False)),
        )


@dataclass
class DeepenCommandState:
    """State for a deepen command (deepen_time_split)."""

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
    # findings_history is a per-iteration ledger written by review_swarm_pr.
    # Each entry: {"iteration": int, "p1": int, "p2": int, "p3": int,
    # "signatures": list[str]}. findings_summary mirrors the last entry.
    # Consumed by the oscillation rule in review_swarm_pr's Convergence
    # Protocol — same (file, category) pair appearing in >=3 distinct
    # iterations triggers CAPPED_BY_OSCILLATION.
    findings_history: list = field(default_factory=list)
    review_reports: list = field(default_factory=list)
    # Signature algorithm version. v2 introduces stopword-strip + casefold
    # normalization (see pipeline-state-schema/SKILL.md "Finding signature
    # algorithm (v2)"). State with version < 2 is migrated on read: legacy
    # signatures are preserved in `legacy_signatures` so oscillation matching
    # can union v1 and v2 sets across the migration boundary. Migration is
    # idempotent — re-loading a v2 state is a no-op.
    signature_version: int = 2
    # Flat list of pre-v2 signatures preserved across migration. Empty for
    # state born under v2.
    legacy_signatures: list = field(default_factory=list)

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
            "findings_history": self.findings_history,
            "review_reports": self.review_reports,
            "signature_version": self.signature_version,
            "legacy_signatures": self.legacy_signatures,
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
        findings_history = list(d.get("findings_history") or [])
        legacy_signatures = list(d.get("legacy_signatures") or [])
        try:
            signature_version = int(d.get("signature_version", 1))
        except (ValueError, TypeError):
            signature_version = 1
        # v1→v2 migration: preserve historical signatures in legacy_signatures so
        # the oscillation matcher can union v1 and v2 sets. We can't recompute
        # legacy signatures (raw title/file/category not stored on pre-v2
        # entries), so the original strings are kept as-is.
        if signature_version < 2 and findings_history:
            seen = set(legacy_signatures)
            for entry in findings_history:
                for sig in entry.get("signatures", []) or []:
                    if sig not in seen:
                        legacy_signatures.append(sig)
                        seen.add(sig)
        signature_version = max(signature_version, 2)
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
            findings_history=findings_history,
            review_reports=list(d.get("review_reports") or []),
            signature_version=signature_version,
            legacy_signatures=legacy_signatures,
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
    bootstrap_converge: MainCommandState = field(default_factory=MainCommandState)
    space_split_converge: MainCommandState = field(default_factory=MainCommandState)
    phase_review: PhaseReview = field(default_factory=PhaseReview)
    plans: dict[str, EpicPlan] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "bootstrap_converge": self.bootstrap_converge.to_dict(),
            "space_split_converge": self.space_split_converge.to_dict(),
            "phase_review": self.phase_review.to_dict(),
            "plans": {k: v.to_dict() for k, v in self.plans.items()},
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> PhaseState:
        if not d:
            return cls()
        plans_raw = d.get("plans") or {}
        plans = {k: EpicPlan.from_dict(v) for k, v in plans_raw.items()}

        # Migration shim: legacy "bootstrap" + "deepen_bootstrap" pair
        # → unified "bootstrap_converge". Findings, locked_skills, and feedback_path
        # are promoted from the old deepen entry to the new converge entry.
        # NOTE: this shim is intentionally short-lived. Once all live
        # pipeline_state.json files have been migrated, delete this block (and
        # the corresponding test in test_models.py) and let unknown keys be
        # silently ignored. The CLI error guards in cmd_next/cmd_complete
        # remain in place permanently to catch stale clients.
        bc_raw = d.get("bootstrap_converge")
        if bc_raw is None and "bootstrap" in d:
            legacy_main = MainCommandState.from_dict(d.get("bootstrap"))
            legacy_deepen = DeepenCommandState.from_dict(d.get("deepen_bootstrap"))
            if legacy_deepen.findings_summary and (
                legacy_deepen.findings_summary.high
                or legacy_deepen.findings_summary.medium
                or legacy_deepen.findings_summary.low
            ):
                legacy_main.findings_summary = legacy_deepen.findings_summary
            if legacy_deepen.locked_skills:
                legacy_main.locked_skills = legacy_deepen.locked_skills
            if legacy_deepen.feedback_path:
                legacy_main.output_paths["feedback_file"] = legacy_deepen.feedback_path
            bootstrap_converge = legacy_main
        else:
            bootstrap_converge = MainCommandState.from_dict(bc_raw)

        # Migration shim: legacy "space_split" + "deepen_space_split" pair
        # → unified "space_split_converge". Same pattern as bootstrap shim above.
        # Short-lived; permanent error guards in subcommands catch stale clients.
        ssc_raw = d.get("space_split_converge")
        if ssc_raw is None and "space_split" in d:
            legacy_main = MainCommandState.from_dict(d.get("space_split"))
            legacy_deepen = DeepenCommandState.from_dict(d.get("deepen_space_split"))
            if legacy_deepen.findings_summary and (
                legacy_deepen.findings_summary.high
                or legacy_deepen.findings_summary.medium
                or legacy_deepen.findings_summary.low
            ):
                legacy_main.findings_summary = legacy_deepen.findings_summary
            if legacy_deepen.locked_skills:
                legacy_main.locked_skills = legacy_deepen.locked_skills
            if legacy_deepen.feedback_path:
                legacy_main.output_paths["feedback_file"] = legacy_deepen.feedback_path
            space_split_converge = legacy_main
        else:
            space_split_converge = MainCommandState.from_dict(ssc_raw)

        return cls(
            bootstrap_converge=bootstrap_converge,
            space_split_converge=space_split_converge,
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

# Closed enum used as bucket key for compound_improve cross-epic Kind-2
# patterns (`(category, threat_class)`) and as a structured field on
# `findings_history.entries[].threat_class`. See
# `pipeline-state-schema/SKILL.md#threat_class--closed-enum` for taxonomy.
THREAT_CLASS_ENUM = frozenset({
    "auth-bypass",
    "injection",
    "data-loss",
    "race-condition",
    "type-escape",
    "permissions",
    "concurrency",
    "secrets-exposure",
    "path-traversal",
    "denial-of-service",
    "crypto-misuse",
    "input-validation",
    "error-handling",
    "resource-leak",
    "other",
})

RECOMMENDATION_MATRIX: dict[str, set[str]] = {
    "time_split": {"bootstrap_converge", "space_split_converge", "plan_epic_converge", "create_issues_from_plan_swarm"},
    "bootstrap_converge": {"space_split_converge", "plan_epic_converge", "create_issues_from_plan_swarm"},
    "space_split_converge": {"plan_epic_converge", "create_issues_from_plan_swarm"},
    "plan_epic_converge": {"create_issues_from_plan_swarm"},
}

MAX_RECOMMENDATIONS_PER_PAIR = 5

DEFAULT_RECOMMENDATIONS = {
    "bootstrap_converge": [],
    "space_split_converge": [],
    "plan_epic_converge": [],
    "create_issues_from_plan_swarm": [],
}
