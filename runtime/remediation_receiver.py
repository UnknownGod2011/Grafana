#!/usr/bin/env python3
"""Loopback-only reference server for StageGuard remediation transport testing.

This receiver demonstrates authentication, strict request parsing, and
server-side idempotency. It never mutates real infrastructure.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY_BYTES = 16 * 1024


class ReferenceRemediationServer(ThreadingHTTPServer):
    def __init__(self, address, token: str) -> None:
        super().__init__(address, ReferenceRemediationHandler)
        self.token = token
        self.operations: dict[str, dict] = {}


class ReferenceRemediationHandler(BaseHTTPRequestHandler):
    server: ReferenceRemediationServer

    def log_message(self, _format: str, *_args) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/v1/recover":
            self._json(404, {"error": "not_found"})
            return
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        if not hmac.compare_digest(auth, expected):
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
        if not isinstance(operation_id, str) or not operation_id.startswith("sg-") or len(operation_id) != 43:
            self._json(400, {"error": "invalid_operation_id"})
            return
        if self.headers.get("Idempotency-Key") != operation_id:
            self._json(409, {"error": "idempotency_key_mismatch"})
            return
        if document.get("action") != "recover_uplink":
            self._json(400, {"error": "unsupported_action"})
            return
        if not all(isinstance(document.get(key), str) and document[key] for key in ("production_id", "target")):
            self._json(400, {"error": "invalid_scope"})
            return

        prior = self.server.operations.get(operation_id)
        if prior is not None and prior != document:
            self._json(409, {"error": "operation_identity_reused_with_different_request"})
            return
        self.server.operations.setdefault(operation_id, dict(document))
        self._json(200, {"accepted": True, "operation_id": operation_id})

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not_found"})

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
