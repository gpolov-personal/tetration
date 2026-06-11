"""eigen-squared CLI — deterministic pipeline state management."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

# Resolve eigen-core via the vendored copy embedded in this plugin. The copy
# is regenerated from plugins/eigen-core/ by tools/vendor-core.sh (invoked
# from the pre-commit hook), so updates to the shared modules land here
# automatically. Keeping a bundled copy means the plugin works after install
# regardless of whether eigen-core is also installed, and regardless of where
# Claude Code places either plugin in its cache.
_vendored = _Path(__file__).resolve().parent.parent / "_vendored"
if _vendored.exists() and str(_vendored) not in _sys.path:
    _sys.path.insert(0, str(_vendored))

__version__ = "3.8.1"
