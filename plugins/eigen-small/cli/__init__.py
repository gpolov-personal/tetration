"""eigen-small CLI — router-driven, single-phase, goal-gated pipeline state.

Thin (~9 permissive verbs) over eigen-core's atomic raw I/O. Deliberately NOT
eigen-squared's 22-verb surface and NOT its strict ordering gate: `small next`
is permissive — it reports the next actionable step from whatever state is
recorded and never refuses a skipped or reordered stage.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

# Resolve eigen-core via the vendored copy embedded in this plugin.
# See plugins/eigen-lite/cli/__init__.py — same model: plugin caches only
# contain the plugin's own subtree, so each consumer bundles its own eigen_core.
_vendored = _Path(__file__).resolve().parent.parent / "_vendored"
if _vendored.exists() and str(_vendored) not in _sys.path:
    _sys.path.insert(0, str(_vendored))

__version__ = "0.4.0"
