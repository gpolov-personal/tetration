"""Tests for the ``cmd_sync_opencode`` subcommand handler.

Focused on the C8 active-runs gate behaviour. The lower-level pieces
(copy, ensemble.json regen, sentinel) are covered in ``test_sync.py``.
"""

from __future__ import annotations

import os
from argparse import Namespace
from pathlib import Path

import pytest

from cli.subcommands import cmd_sync_opencode


def _stub_opencode_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Place a no-op ``opencode`` binary on PATH so the pre-flight passes."""
    bindir = tmp_path / "stubbin"
    bindir.mkdir()
    (bindir / "opencode").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "opencode").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH','')}")


def test_cmd_sync_opencode_fails_closed_on_unreachable_daemon(
    tmp_path, monkeypatch, capsys
):
    """Pins must-fix #3 from PR #33 review.

    Pre-fix behaviour: a daemon transport error produced
    ``WARNING: ... Proceeding without C8 check`` and continued. With
    ``rmtree``-then-``copytree`` semantics in :func:`sync.copy_assets`,
    this lets a sync corrupt a live opencode run if the daemon happens
    to be down/firewalled. Fail-closed makes the operator opt in to
    that risk via ``--skip-active-check``.
    """
    # Build a plausible eigen-root: a directory exists but the daemon URL
    # we point at is bound to nothing (port 1).
    root = tmp_path / "init"
    root.mkdir()
    (root / ".eigen").mkdir()

    _stub_opencode_on_path(tmp_path, monkeypatch)

    args = Namespace(
        root=str(root),
        tasks_api="http://127.0.0.1:1",  # guaranteed-unreachable
        skip_active_check=False,
    )
    rc = cmd_sync_opencode(args)
    assert rc == 1, "expected EXIT_ERROR when daemon is unreachable"

    err = capsys.readouterr().err
    assert "could not query active runs" in err
    assert "--skip-active-check" in err

    # And critically: the sync did NOT touch .opencode/ because we
    # bailed before any rmtree/copy. (No .opencode/ dir at all here.)
    assert not (root / ".opencode" / "commands").exists()


def test_cmd_sync_opencode_fails_closed_on_invalid_json(
    tmp_path, monkeypatch, capsys
):
    """Same fail-closed contract when the daemon returns garbage."""
    import http.server, threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"not json at all")

        def log_message(self, *_a, **_k):  # silence
            return

    httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        port = httpd.server_address[1]
        root = tmp_path / "init"
        root.mkdir()
        (root / ".eigen").mkdir()

        _stub_opencode_on_path(tmp_path, monkeypatch)

        args = Namespace(
            root=str(root),
            tasks_api=f"http://127.0.0.1:{port}",
            skip_active_check=False,
        )
        rc = cmd_sync_opencode(args)
        assert rc == 1
        err = capsys.readouterr().err
        # check_active_runs reports parse errors distinctly from
        # transport errors — both still trip the fail-closed gate.
        assert "non-JSON response" in err
        assert "--skip-active-check" in err
    finally:
        httpd.shutdown()


def test_cmd_sync_opencode_skip_active_check_bypasses_gate(
    tmp_path, monkeypatch, capsys
):
    """``--skip-active-check`` is the documented escape hatch.

    With it set, the C8 query is skipped entirely; the sync proceeds
    to the actual asset copy (which will then fail because the plugin
    source / asset trees aren't really wired in this test, but that
    failure is unrelated to C8 — proving the gate was bypassed).
    """
    root = tmp_path / "init"
    root.mkdir()
    (root / ".eigen").mkdir()

    _stub_opencode_on_path(tmp_path, monkeypatch)

    args = Namespace(
        root=str(root),
        tasks_api="http://127.0.0.1:1",  # would normally fail-closed
        skip_active_check=True,
    )
    # We don't care whether it returns 0 or 1 — only that the C8 error
    # message is NOT in stderr.
    cmd_sync_opencode(args)
    err = capsys.readouterr().err
    assert "could not query active runs" not in err
