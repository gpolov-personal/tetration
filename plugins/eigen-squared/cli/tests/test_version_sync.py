"""Guardrail: plugin.json version must equal cli/__init__.py __version__.

Same rationale as plugins/eigen-lite/cli/tests/test_version_sync.py — the
marketplace reads plugin.json, `eigen-squared --version` reads
__version__, and the wrapper script embeds the version at install time.
This test fails CI when they drift.
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
        f"If the wrapper script at ~/.local/bin/eigen-squared is stale, "
        f"run /eigen_start --reinstall-cli-only on affected machines."
    )
