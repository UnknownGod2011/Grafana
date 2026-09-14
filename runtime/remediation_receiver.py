#!/usr/bin/env python3
"""Loopback-only reference server for StageGuard remediation transport testing.

This receiver demonstrates authentication, strict request parsing, server-side
idempotency, and read-only provider reconciliation. It never mutates real
infrastructure.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY_BYTES = 16 * 1024
_OPERATION_PREFIX = "/v1/operations/"


class ReferenceRemediationServer(ThreadingHTTPServer):
    def __init__(self, address, token: str) -> None:
        super().__init__(address, ReferenceRemediationHandler)
        self.token = token
        self.operations: dict[str, dict] = {}
        # ThreadingHTTPServer may process duplicate idempotency keys concurrently.
        # Check-and-store therefore has to be one critical section; otherwise two
        # different requests can both observe an absent operation and both report
        # acceptance even though only one mutation identity is retained.
        self.operations_lock = threading.Lock()


class ReferenceRemediationHandler(BaseHTTPRequestHandler):
    server: ReferenceRemediationServer

    def log_message(self, _format: str, *_args) -> None:
        return

    def _authenticated(self) -> bool:
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        return hmac.compare_digest(auth, expected)

    @staticmethod
    def _valid_operation_id(value: object) -> bool:
        return isinstance(value, str) and value.startswith("sg-") and len(value) == 43

    def do_POST(self) -> None:
        if self.path != "/v1/recover":
            self._json(404, {"error": "not_found"})
            return
        if not self._authenticated():
            self._json(401, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": "invalid_body_size"})
            return

        try:
            document = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "invalid_json"})
            return

        required = {"operation_id", "action", "production_id", "target"}
        if not isinstance(document, dict) or set(document) != required:
            self._json(400, {"error": "invalid_schema"})
            return
        operation_id = document.get("operation_id")
        if not self._valid_operation_id(operation_id):
            self._json(400, {"error": "invalid_operation_id"})
            return
        assert isinstance(operation_id, str)
        if self.headers.get("Idempotency-Key") != operation_id:
            self._json(409, {"error": "idempotency_key_mismatch"})
            return
        if document.get("action") != "recover_uplink":
            self._json(400, {"error": "unsupported_action"})
            return
        if not all(isinstance(document.get(key), str) and document[key] for key in ("production_id", "target")):
            self._json(400, {"error": "invalid_scope"})
            return

        with self.server.operations_lock:
            prior = self.server.operations.get(operation_id)
            if prior is None:
                self.server.operations[operation_id] = dict(document)
                conflict = False
            else:
                conflict = prior != document

        if conflict:
            self._json(409, {"error": "operation_identity_reused_with_different_request"})
            return
        self._json(200, {"accepted": True, "operation_id": operation_id})

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(200, {"ok": True})
            return

        if not self.path.startswith(_OPERATION_PREFIX):
            self._json(404, {"error": "not_found"})
            return
        if not self._authenticated():
            self._json(401, {"error": "unauthorized"})
            return

        operation_id = self.path[len(_OPERATION_PREFIX):]
        if not self._valid_operation_id(operation_id):
            self._json(400, {"error": "invalid_operation_id"})
            return

        with self.server.operations_lock:
            accepted = operation_id in self.server.operations
        if accepted:
            self._json(200, {"operation_id": operation_id, "state": "accepted"})
            return
        self._json(404, {"operation_id": operation_id, "state": "not_found"})

    def _json(self, status: int, document: dict) -> None:
        body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the loopback StageGuard remediation contract receiver")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9120)
    parser.add_argument("--token-env", default="STAGEGUARD_REFERENCE_REMEDIATION_TOKEN")
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("reference remediation receiver is loopback-only")
    token = os.getenv(args.token_env, "")
    if not token:
        parser.error(f"required environment variable {args.token_env} is not set")
    server = ReferenceRemediationServer((args.host, args.port), token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
