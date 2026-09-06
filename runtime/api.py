#!/usr/bin/env python3
"""Minimal HTTP API for the bounded StageGuard incident service.

No endpoint accepts PromQL, datasource identifiers, remediation action names,
or arbitrary targets. The API only exposes the deterministic lifecycle already
implemented by ``IncidentService``.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from incident_service import IncidentService


MAX_BODY_BYTES = 16 * 1024


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if length < 0 or length > MAX_BODY_BYTES:
        raise ValueError("request body too large")
    if length == 0:
        return {}
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.lower().startswith("application/json"):
        raise ValueError("Content-Type must be application/json")
    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def _only(payload: dict[str, Any], allowed: set[str]) -> None:
    unexpected = set(payload) - allowed
    if unexpected:
        raise ValueError(f"unsupported fields: {', '.join(sorted(unexpected))}")


class StageGuardHandler(BaseHTTPRequestHandler):
    service: IncidentService
    server_version = "StageGuard/0.1"

    def log_message(self, _format: str, *_args: object) -> None:
        # Host applications should provide structured request logging. Avoid
        # emitting operator identifiers or request bodies via default stderr.
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, detail: str) -> None:
        self._send(status, {"error": code, "detail": detail})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, {"ok": True})
            return
        if self.path != "/v1/incident":
            self._error(404, "not_found", "unknown endpoint")
            return
        snapshot = self.service.status()
        self._send(200, {"incident": None if snapshot is None else snapshot.to_dict()})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = _read_json(self)
            if self.path == "/v1/investigate":
                _only(payload, {"actor"})
                actor = payload.get("actor", "stageguard")
                if not isinstance(actor, str):
                    raise ValueError("actor must be a string")
                snapshot = self.service.investigate(actor=actor)
                self._send(200, {"incident": snapshot.to_dict()})
                return

            if self.path == "/v1/approve":
                _only(payload, {"incident_id", "revision", "approved_by"})
                required = ("incident_id", "revision", "approved_by")
                if any(not isinstance(payload.get(name), str) for name in required):
                    raise ValueError("incident_id, revision, and approved_by are required strings")
                snapshot = self.service.approve(
                    incident_id=payload["incident_id"],
                    revision=payload["revision"],
                    approved_by=payload["approved_by"],
                )
                self._send(200, {"incident": snapshot.to_dict()})
                return

            if self.path == "/v1/execute":
                _only(payload, {"actor"})
                actor = payload.get("actor", "stageguard")
                if not isinstance(actor, str):
                    raise ValueError("actor must be a string")
                snapshot = self.service.execute_approved(actor=actor)
                self._send(200, {"incident": snapshot.to_dict()})
                return

            self._error(404, "not_found", "unknown endpoint")
        except ValueError as exc:
            self._error(400, "invalid_request", str(exc))
        except RuntimeError as exc:
            self._error(409, "invalid_state", str(exc))
        except Exception:
            # Do not leak internal transport/credential details to callers.
            self._error(500, "internal_error", "request failed")


def serve(service: IncidentService, host: str = "127.0.0.1", port: int = 9110) -> None:
    """Serve a preconfigured StageGuard service. Loopback is the safe default."""
    handler = type("ConfiguredStageGuardHandler", (StageGuardHandler,), {"service": service})
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()
