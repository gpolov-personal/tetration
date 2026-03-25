"""Epic DAG loading and dependency checking.

Ported from hooks/pipeline_controller.py (lines 492-539).
"""

from __future__ import annotations

import json
from pathlib import Path


def load_epic_order(phase_num: int, eigen_root: str = "") -> list[int]:
    """Load epic execution order from epic_dag.json.

    Epics are returned in wave order: all wave-1 epics first, then wave-2, etc.
    Returns empty list if epic_dag.json doesn't exist or is invalid.
    """
    if not eigen_root:
        return []
    dag_path = (
        Path(eigen_root)
        / f"eigen_initiative/phases/phase_{phase_num}/epic_dag.json"
    )
    if not dag_path.exists():
        return []
    try:
        dag = json.loads(dag_path.read_text())
        order: list[int] = []
        for wave_key in sorted(dag.get("waves", {}).keys()):
            order.extend(dag["waves"][wave_key])
        return order
    except (json.JSONDecodeError, KeyError):
        return []


def epic_dependencies_met(
    phase: dict,
    epic_num: int,
    phase_num: int,
    eigen_root: str = "",
) -> bool:
    """Check if all of an epic's DAG dependencies (blocked_by) are converged."""
    if not eigen_root:
        return False
    dag_path = (
        Path(eigen_root)
        / f"eigen_initiative/phases/phase_{phase_num}/epic_dag.json"
    )
    if not dag_path.exists():
        return False
    try:
        dag = json.loads(dag_path.read_text())
        for epic in dag.get("epics", []):
            if epic.get("number") == epic_num:
                for blocker_num in epic.get("blocked_by", []):
                    blocker = phase.get("plans", {}).get(str(blocker_num))
                    if blocker is None:
                        return False
                    swarm_converged = (
                        blocker.get("swarm_execution", {})
                        .get("convergence", {})
                        .get("converged", False)
                    )
                    if not swarm_converged:
                        return False
                return True  # All blockers converged (or no blockers)
        return False  # Epic not found in DAG
    except (json.JSONDecodeError, KeyError):
        return False
