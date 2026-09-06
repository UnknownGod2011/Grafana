#!/usr/bin/env python3
"""Minimal authenticated HTTP API for the bounded StageGuard incident service.

No endpoint accepts PromQL, datasource identifiers, remediation action names,
or arbitrary targets. Mutating lifecycle operations derive actor identity from
a configured ``IdentityProvider`` rather than caller-controlled JSON fields.
"""
from __future__ import annotations

import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from identity import AuthenticationError, IdentityProvider, LocalDevelopmentIdentityProvider, OperatorIdentity
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


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class StageGuardHandler(BaseHTTPRequestHandler):
    service: IncidentService
    identity_provider: IdentityProvider
    server_version = "StageGuard/0.2"

    def log_message(self, _format: str, *_args: object) -> None:
        # Host applications should provide structured request logging. Avoid
        # emitting credentials, operator identifiers, or request bodies.
        return

    def _send(self, status: int, payload: dict[str, Any], *, authenticate: bool = False) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if authenticate:
            self.send_header("WWW-Authenticate", 'Bearer realm="stageguard"')
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, detail: str, *, authenticate: bool = False) -> None:
        self._send(status, {"error": code, "detail": detail}, authenticate=authenticate)

    def _identity(self) -> OperatorIdentity:
        return self.identity_provider.authenticate(self)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, {"ok": True})
            return
        if self.path != "/v1/incident":
            self._error(404, "not_found", "unknown endpoint")
            return
        try:
            self._identity()
        except AuthenticationError as exc:
            self._error(401, "unauthorized", str(exc), authenticate=True)
            return
        snapshot = self.service.status()
        self._send(200, {"incident": None if snapshot is None else snapshot.to_dict()})

    def do_POST(self) -> None:  # noqa: N802
        try:
            identity = self._identity()
            payload = _read_json(self)

            if self.path == "/v1/investigate":
                _only(payload, set())
                snapshot = self.service.investigate(actor=identity.subject)
                self._send(200, {"incident": snapshot.to_dict()})
                return

            if self.path == "/v1/approve":
                _only(payload, {"incident_id", "revision"})
                required = ("incident_id", "revision")
                if any(not isinstance(payload.get(name), str) for name in required):
                    raise ValueError("incident_id and revision are required strings")
                snapshot = self.service.approve(
                    incident_id=payload["incident_id"],
                    revision=payload["revision"],
                    approved_by=identity.subject,
                )
                self._send(200, {"incident": snapshot.to_dict()})
                return

            if self.path == "/v1/execute":
                _only(payload, set())
                snapshot = self.service.execute_approved(actor=identity.subject)
                self._send(200, {"incident": snapshot.to_dict()})
                return

            self._error(404, "not_found", "unknown endpoint")
        except AuthenticationError as exc:
            self._error(401, "unauthorized", str(exc), authenticate=True)
        except ValueError as exc:
            self._error(400, "invalid_request", str(exc))
        except RuntimeError as exc:
            self._error(409, "invalid_state", str(exc))
        except Exception:
            # Do not leak internal transport/credential details to callers.
            self._error(500, "internal_error", "request failed")


def make_server(
    service: IncidentService,
    host: str = "127.0.0.1",
    port: int = 9110,
    *,
    identity_provider: IdentityProvider | None = None,
) -> ThreadingHTTPServer:
    """Construct a server while enforcing the network/authentication boundary.

    Local development gets a fixed process-configured identity on loopback. A
    non-loopback bind requires an explicitly configured non-development
    provider; accidental exposure with implicit/local identity fails closed.
    """
    provider = identity_provider or LocalDevelopmentIdentityProvider()
    if not _is_loopback(host) and provider.is_development_only:
        raise ValueError("non-loopback bind requires an explicit production-capable identity provider")
    handler = type(
        "ConfiguredStageGuardHandler",
        (StageGuardHandler,),
        {"service": service, "identity_provider": provider},
    )
    return ThreadingHTTPServer((host, port), handler)


def serve(
    service: IncidentService,
    host: str = "127.0.0.1",
    port: int = 9110,
    *,
    identity_provider: IdentityProvider | None = None,
) -> None:
    """Serve StageGuard with loopback-safe local identity by default."""
    make_server(service, host, port, identity_provider=identity_provider).serve_forever()
