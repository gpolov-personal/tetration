"""Cross-phase freeze ledger: add/list round-trip + idempotency on (name, phase)."""

import os
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from cli.freeze_ledger import Seam, add_seam, load_ledger, save_ledger  # noqa: E402


def test_empty_ledger_when_absent() -> None:
    with tempfile.TemporaryDirectory() as d:
        assert load_ledger(os.path.join(d, "nope.json")).seams == []


def test_add_list_round_trip() -> None:
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "freeze.json")
        led = load_ledger(f)
        add_seam(led, Seam(name="PromptEgressInputs", phase=1, kind="hook",
                           signature="transform(ctx)->ctx", consumers=["PII-01"]))
        save_ledger(led, f)
        again = load_ledger(f)
        assert len(again.seams) == 1
        s = again.seams[0]
        assert s.name == "PromptEgressInputs" and s.phase == 1 and s.kind == "hook"
        assert s.consumers == ["PII-01"]
        assert s.recorded_at  # stamped on add


def test_add_is_idempotent_on_name_phase() -> None:
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "freeze.json")
        led = load_ledger(f)
        add_seam(led, Seam(name="X", phase=1, signature="v1"))
        add_seam(led, Seam(name="X", phase=1, signature="v2"))  # replaces same (name, phase)
        assert len(led.seams) == 1
        assert led.seams[0].signature == "v2"
        add_seam(led, Seam(name="X", phase=2))  # same name, different phase = distinct
        assert len(led.seams) == 2
