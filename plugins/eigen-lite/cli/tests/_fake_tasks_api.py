"""In-process claude-tasks-compatible HTTP server for integration tests.

This is NOT a mock — it's a real HTTP server running on localhost that
implements the subset of endpoints eigen-lite uses (POST /api/v1/tasks and
GET /api/v1/tasks). Tests talk to it exactly the way they'd talk to the
production claude-tasks service, exercising the full curl → POST → JSON
round-trip (incl. subprocess invocation). A Docker-based claude-tasks run
would only differ in where the server lives; the wire protocol is identical.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional


class FakeTasksAPI:
    """Tiny HTTP server that stores POSTed tasks in memory.

    Usage:
        with FakeTasksAPI() as api:
            url = api.url
            # ... point CLAUDE_TASKS_API at url ...
            assert api.tasks == [...]
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.tasks: list[dict] = []
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._next_id = 1

    def _make_handler(self):
        api_self = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status: int, body: dict | list) -> None:
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):  # noqa: N802  (stdlib naming)
                if self.path == "/api/v1/tasks":
                    with api_self._lock:
                        self._send_json(200, {"tasks": list(api_self.tasks)})
                    return
                self._send_json(404, {"error": "not found"})

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "invalid json"})
                    return

                if self.path == "/api/v1/tasks":
                    with api_self._lock:
                        body.setdefault("id", api_self._next_id)
                        api_self._next_id += 1
                        body.setdefault("last_run_status", "pending")
                        api_self.tasks.append(body)
                    self._send_json(201, body)
                    return

                if self.path == "/api/v1/notify":
                    # Just ack — we don't need to inspect notify payloads in
                    # the current tests, but we accept them to avoid failures.
                    self._send_json(200, {"ok": True})
                    return

                self._send_json(404, {"error": "not found"})

            def log_message(self, format: str, *args):  # noqa: A002
                # Silence the default stderr spam during tests.
                pass

        return Handler

    def __enter__(self) -> "FakeTasksAPI":
        self._server = HTTPServer((self.host, self.port), self._make_handler())
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def mark_running(self, working_dir: str) -> None:
        """Flip an existing task into 'running' status for that project."""
        with self._lock:
            for t in self.tasks:
                if t.get("working_dir") == working_dir:
                    t["last_run_status"] = "running"

    def reset(self) -> None:
        with self._lock:
            self.tasks.clear()
            self._next_id = 1
