"""eigen-lite CLI — single-phase, multi-epic pipeline state management."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

# Resolve eigen-core via the vendored copy embedded in this plugin.
# See plugins/eigen-squared/cli/__init__.py for the rationale — same model.
_vendored = _Path(__file__).resolve().parent.parent / "_vendored"
if _vendored.exists() and str(_vendored) not in _sys.path:
    _sys.path.insert(0, str(_vendored))

__version__ = "0.1.0"
