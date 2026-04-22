"""Typed data models for eigen-lite pipeline_state.json.

Single-phase, multi-epic schema. Flat compared to eigen-squared: there is no
``phases[<N>]`` layer — just ``lite_plan`` and an ``epics`` dict keyed by
epic number (``"1"``, ``"2"``, ...). Primitives like ``Convergence`` and
``FindingsSummary`` come from ``eigen_core.cli.base_models`` via the vendored
copy under ``_vendored/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from eigen_core.cli.base_models import Convergence, FindingsSummary

# Explicit alias per plan §8 Sprint 2 point 3. Lets consumers depend on a
# schema-namespaced name that won't break if core renames its primitive.
LiteConvergence = Convergence

# Distinct state file location from squared's `eigen_initiative/phases/
# pipeline_state.json`. Keeping the same parent directory (`phases/`) lets
# squared and lite share the per-epic artifact tree the workers consume
# (phases/phase_1/epic_<M>/...); only the root state file is separated.
LITE_STATE_RELATIVE_PATH = "eigen_initiative/phases/pipeline_state_lite.json"


class SquaredSchemaDetected(ValueError):
    """Raised when LitePipelineState.from_dict is handed a squared-shaped dict.

    Prevents silent overwrite of squared's pipeline_state.json if a user
    accidentally points lite at squared's state file (e.g. misconfigured
    EIGEN_ROOT or running lite in a squared-initialized repo).
    """


def _default_plan_output_paths() -> dict:
    return {
        "phase_manifest": None,
        "bootstrap_report": None,
        "epic_manifest": None,
        "phase_e2e_config": None,
    }


def _default_review_findings() -> dict:
    return {"p1": 0, "p2": 0, "p3": 0}


# ---------------------------------------------------------------------------
# LitePlanState — single condensed planning command with internal stages
# ---------------------------------------------------------------------------

@dataclass
class LitePlanState:
    """State for the monolithic `lite_plan` command.

    ``stages_completed`` is the idempotency key: Stage E entries look like
    ``"E:1"``, ``"E:2"``, ... (one per epic). A re-run reads this list and
    resumes from the first missing stage.
    """

    status: str = "not_started"  # not_started | in_progress | completed
    iteration: int = 0
    stages_completed: list[str] = field(default_factory=list)
    output_paths: dict = field(default_factory=_default_plan_output_paths)
    findings_summary: FindingsSummary = field(default_factory=FindingsSummary)
    convergence: Convergence = field(default_factory=Convergence)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "iteration": self.iteration,
            "stages_completed": list(self.stages_completed),
            "output_paths": dict(self.output_paths),
            "findings_summary": self.findings_summary.to_dict(),
            "convergence": self.convergence.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "LitePlanState":
        if not d:
            return cls()
        output_paths = _default_plan_output_paths()
        output_paths.update(d.get("output_paths") or {})
        return cls(
            status=d.get("status", "not_started"),
            iteration=int(d.get("iteration", 0)),
            stages_completed=list(d.get("stages_completed") or []),
            output_paths=output_paths,
            findings_summary=FindingsSummary.from_dict(d.get("findings_summary")),
            convergence=Convergence.from_dict(d.get("convergence")),
        )


# ---------------------------------------------------------------------------
# LiteSwarmExecution — per-epic orchestrate+fix loop
# ---------------------------------------------------------------------------

@dataclass
class LiteSwarmExecution:
    status: str = "not_started"  # not_started | pr_created | iterating | converged
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    integration_branch: Optional[str] = None
    convergence: Convergence = field(default_factory=Convergence)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "integration_branch": self.integration_branch,
            "convergence": self.convergence.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "LiteSwarmExecution":
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
            pr_url=d.get("pr_url"),
            pr_number=pr_number,
            integration_branch=d.get("integration_branch"),
            convergence=Convergence.from_dict(d.get("convergence")),
        )


# ---------------------------------------------------------------------------
# LiteReviewState — per-epic review agent ensemble
# ---------------------------------------------------------------------------

@dataclass
class LiteReviewState:
    """State for the `lite_review` command, per epic.

    ``findings_summary`` is priority-shaped (``p1``/``p2``/``p3``) to mirror
    squared's ``SwarmExecution`` — intentionally different from
    ``LitePlanState.findings_summary`` which is severity-shaped
    (``high``/``medium``/``low``).
    """

    status: str = "not_started"  # not_started | in_progress | complete
    review_iteration: int = 0
    findings_summary: dict = field(default_factory=_default_review_findings)
    convergence: Convergence = field(default_factory=Convergence)
    review_reports: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "review_iteration": self.review_iteration,
            "findings_summary": dict(self.findings_summary),
            "convergence": self.convergence.to_dict(),
            "review_reports": list(self.review_reports),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "LiteReviewState":
        if not d:
            return cls()
        findings = _default_review_findings()
        findings.update(d.get("findings_summary") or {})
        return cls(
            status=d.get("status", "not_started"),
            review_iteration=int(d.get("review_iteration", 0)),
            findings_summary=findings,
            convergence=Convergence.from_dict(d.get("convergence")),
            review_reports=list(d.get("review_reports") or []),
        )


# ---------------------------------------------------------------------------
# LiteEpicState — per-epic container
# ---------------------------------------------------------------------------

@dataclass
class LiteEpicState:
    epic_path: Optional[str] = None
    epic_file: Optional[str] = None
    plan_file: Optional[str] = None
    swarm_manifest: Optional[str] = None
    is_e2e_epic: bool = False
    lite_swarm: LiteSwarmExecution = field(default_factory=LiteSwarmExecution)
    lite_review: LiteReviewState = field(default_factory=LiteReviewState)

    def to_dict(self) -> dict:
        return {
            "epic_path": self.epic_path,
            "epic_file": self.epic_file,
            "plan_file": self.plan_file,
            "swarm_manifest": self.swarm_manifest,
            "is_e2e_epic": self.is_e2e_epic,
            "lite_swarm": self.lite_swarm.to_dict(),
            "lite_review": self.lite_review.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "LiteEpicState":
        if not d:
            return cls()
        return cls(
            epic_path=d.get("epic_path"),
            epic_file=d.get("epic_file"),
            plan_file=d.get("plan_file"),
            swarm_manifest=d.get("swarm_manifest"),
            is_e2e_epic=bool(d.get("is_e2e_epic", False)),
            lite_swarm=LiteSwarmExecution.from_dict(d.get("lite_swarm")),
            lite_review=LiteReviewState.from_dict(d.get("lite_review")),
        )


# ---------------------------------------------------------------------------
# LitePipelineState — root
# ---------------------------------------------------------------------------

@dataclass
class LitePipelineState:
    """Root model for eigen-lite pipeline_state.json."""

    schema_version: str = "1.0.0"
    feature_set: str = ""
    phase: int = 1  # Always 1 — kept as an explicit field so consumers don't special-case
    epic_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    lite_plan: LitePlanState = field(default_factory=LitePlanState)
    epics: dict[str, LiteEpicState] = field(default_factory=dict)
    recommendations: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "feature_set": self.feature_set,
            "phase": self.phase,
            "epic_count": self.epic_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": {
                "lite_plan": self.lite_plan.to_dict(),
                "epics": {k: v.to_dict() for k, v in self.epics.items()},
            },
            "recommendations": list(self.recommendations),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "LitePipelineState":
        if not d:
            return cls()

        # H1 guard: refuse to silently re-shape squared's state into lite's.
        version = str(d.get("schema_version", ""))
        if version.startswith("2."):
            raise SquaredSchemaDetected(
                f"schema_version {version!r} belongs to eigen-squared; "
                "eigen-lite expects schema_version 1.x"
            )
        state_section = d.get("state") or {}
        if "time_split" in state_section or "phases" in state_section:
            raise SquaredSchemaDetected(
                "state dict carries squared-only keys (time_split/phases); "
                "refusing to parse as lite to avoid overwriting squared state"
            )

        epic_count_raw = d.get("epic_count", 0)
        try:
            epic_count = int(epic_count_raw)
        except (ValueError, TypeError):
            epic_count = 0

        phase_raw = d.get("phase", 1)
        try:
            phase = int(phase_raw)
        except (ValueError, TypeError):
            phase = 1

        state = d.get("state") or {}
        epics_raw = state.get("epics") or {}

        return cls(
            schema_version=d.get("schema_version", "1.0.0"),
            feature_set=d.get("feature_set", ""),
            phase=phase,
            epic_count=epic_count,
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
            lite_plan=LitePlanState.from_dict(state.get("lite_plan")),
            epics={k: LiteEpicState.from_dict(v) for k, v in epics_raw.items()},
            recommendations=list(d.get("recommendations") or []),
        )


# ---------------------------------------------------------------------------
# Status constants — used by validator in Sprint 2.3
# ---------------------------------------------------------------------------

VALID_LITE_PLAN_STATUSES = {"not_started", "in_progress", "completed"}
VALID_LITE_SWARM_STATUSES = {"not_started", "pr_created", "iterating", "converged"}
VALID_LITE_REVIEW_STATUSES = {"not_started", "in_progress", "complete"}
