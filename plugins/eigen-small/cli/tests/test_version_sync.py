"""CI guard: plugin.json version must equal cli/__init__.py __version__.

Mirrors the eigen-squared/eigen-lite convention. Self-contained — parses both
files textually so it needs no import path setup.
"""

import json
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]  # cli/tests -> cli -> plugin root


def test_version_sync() -> None:
    manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    init_src = (PLUGIN_ROOT / "cli" / "__init__.py").read_text()
    match = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", init_src)
    assert match, "no __version__ found in cli/__init__.py"
    assert manifest["version"] == match.group(1), (
        f"plugin.json version {manifest['version']!r} != "
        f"cli __version__ {match.group(1)!r}"
    )
