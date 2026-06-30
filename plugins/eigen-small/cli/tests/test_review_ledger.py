"""Cross-phase review ledger: set/list round-trip, idempotency on phase, all_approved gate."""

import os
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from cli.review_ledger import (  # noqa: E402
    Review,
    all_approved,
    load_ledger,
    save_ledger,
    set_review,
)


def test_empty_ledger_when_absent() -> None:
    with tempfile.TemporaryDirectory() as d:
        assert load_ledger(os.path.join(d, "nope.json")).reviews == []


def test_set_list_round_trip() -> None:
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "review.json")
        led = load_ledger(f)
        set_review(led, Review(phase=1, status="approved", note="specs + goals look right"))
        save_ledger(led, f)
        again = load_ledger(f)
        assert len(again.reviews) == 1
        r = again.reviews[0]
        assert r.phase == 1 and r.status == "approved"
        assert r.note == "specs + goals look right"
        assert r.reviewed_at  # stamped on set


def test_set_is_idempotent_on_phase() -> None:
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "review.json")
        led = load_ledger(f)
        set_review(led, Review(phase=1, status="pending"))
        set_review(led, Review(phase=1, status="approved"))  # replaces same phase
        assert len(led.reviews) == 1
        assert led.reviews[0].status == "approved"
        set_review(led, Review(phase=2, status="approved"))  # distinct phase
        assert len(led.reviews) == 2


def test_all_approved_gate() -> None:
    led = load_ledger(os.path.join(tempfile.gettempdir(), "does-not-exist-review.json"))
    # empty phase list = nothing to run = not approved
    assert all_approved(led, []) is False
    set_review(led, Review(phase=1, status="approved"))
    set_review(led, Review(phase=2, status="pending"))
    assert all_approved(led, [1]) is True
    assert all_approved(led, [1, 2]) is False        # phase 2 still pending
    assert all_approved(led, [1, 3]) is False        # phase 3 has no entry
    set_review(led, Review(phase=2, status="approved"))
    assert all_approved(led, [1, 2]) is True
