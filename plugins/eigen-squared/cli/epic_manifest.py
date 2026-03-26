"""Epic manifest loading — sequential epic ordering.

Epics execute sequentially (E1 → E2 → ... → EN). No parallel waves, no
blocked_by dependencies. The epic_manifest.json contains a flat
`execution_order` array.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_epic_order(phase_num: int, eigen_root: str = "") -> list[int]:
    """Load epic execution order from epic_manifest.json.

    Returns epics as a list of epic numbers in execution order.
    Sequential: simply [1, 2, 3, ..., N].
    """
    if not eigen_root:
        return []

    path = (
        Path(eigen_root)
        / f"eigen_initiative/phases/phase_{phase_num}/epic_manifest.json"
    )
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text())
        order: list[int] = []
        for epic_id in data.get("execution_order", []):
            # Parse "P1.E2" → 2
            parts = epic_id.split(".")
            if len(parts) == 2 and parts[1].startswith("E"):
                try:
                    order.append(int(parts[1][1:]))
                except ValueError:
                    continue
        return order
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
