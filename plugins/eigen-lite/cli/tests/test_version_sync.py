"""Guardrail: plugin.json version must equal cli/__init__.py __version__.

Two sources of truth are inevitable (plugin.json is consumed by the Claude
Code marketplace; __version__ is consumed by `eigen-lite --version` and the
wrapper script installed by /lite_start). This test fails CI when they
drift so the version bump PR can be corrected before merge.
"""

import json
from pathlib import Path

from cli import __version__


PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


def test_plugin_json_version_matches_cli_init():
    plugin_json = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
    )
    assert plugin_json["version"] == __version__, (
        f"Version drift: plugin.json says {plugin_json['version']!r}, "
        f"cli/__init__.py says {__version__!r}. Bump both in the same PR. "
        f"If the wrapper script at ~/.local/bin/eigen-lite is stale, run "
        f"/lite_start --reinstall-cli-only on affected machines."
    )
