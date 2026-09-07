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
from urllib.parse import parse_qs, urlsplit

from identity import AuthenticationError, IdentityProvider, LocalDevelopmentIdentityProvider, OperatorIdentity
from incident_service import IncidentService
from operator_console import CONSOLE_CSS, CONSOLE_HTML, CONSOLE_JS
from readiness import EvidencePlaneReadinessProbe


MAX_BODY_BYTES = 16 * 1024
_EXECUTION_RECONCILIATION_STATES = {"clear", "reload_required", "reloaded"}


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


def _get_readiness_probe(service: IncidentService) -> EvidencePlaneReadinessProbe:
    """Return one service-owned probe so external Grafana checks can be cached."""
    probe = getattr(service, "_readiness_probe", None)
    if probe is None:
        probe = EvidencePlaneReadinessProbe(
            service._profile,
            service._activation,
            service._log_activation,
            service._metrics,
            service._logs,
        )
        setattr(service, "_readiness_probe", probe)
    return probe


def _execution_reconciliation_state(service: IncidentService) -> str:
    """Return the operator-safe, low-cardinality reconciliation phase.

    Base runtimes do not have an execution-uncertainty state machine, so they are
    always ``clear``. A safer runtime may expose the bounded method. Any
    unexpected value fails closed to ``reload_required`` rather than leaking
    provider details or accidentally enabling reconciliation.
    """
    getter = getattr(service, "execution_reconciliation_state", None)
    if not callable(getter):
        return "clear"
    try:
        state = getter()
    except Exception:
        return "reload_required"
    return state if state in _EXECUTION_RECONCILIATION_STATES else "reload_required"


def _lifecycle_view(service: IncidentService, snapshot=None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = service.status()
    return {
        "incident": None if snapshot is None else snapshot.to_dict(),
        "checkpoint_state": service.checkpoint_state(),
        "execution_reconciliation_state": _execution_reconciliation_state(service),
    }


def _service_readiness(service: IncidentService) -> dict[str, object]:
    """Build a bounded readiness view from evidence-plane and lifecycle consistency state."""
    readiness = _get_readiness_probe(service).check().to_dict()
    checkpoint_state = service.checkpoint_state()
    readiness["checks"]["checkpoint"] = checkpoint_state
    if checkpoint_state in {"conflicted", "execution_uncertain"}:
        readiness["ready"] = False
    return readiness


def _service_metrics(service: IncidentService) -> str:
    metrics = _get_readiness_probe(service).prometheus_metrics()
    checkpoint_store = getattr(service, "_checkpoint_store", None)
    exporter = getattr(checkpoint_store, "prometheus_metrics", None)
    if callable(exporter):
        metrics += exporter()
    checkpoint_state = service.checkpoint_state()
    conflict_blocked = 1 if checkpoint_state == "conflicted" else 0
    execution_uncertain = 1 if checkpoint_state == "execution_uncertain" else 0
    metrics += (
        "# HELP stageguard_checkpoint_conflict_blocked Whether lifecycle mutation is blocked pending explicit checkpoint reload.\n"
        "# TYPE stageguard_checkpoint_conflict_blocked gauge\n"
        f"stageguard_checkpoint_conflict_blocked {conflict_blocked}\n"
        "# HELP stageguard_remediation_execution_uncertain Whether remediation provider execution is ambiguous and lifecycle work is blocked.\n"
        "# TYPE stageguard_remediation_execution_uncertain gauge\n"
        f"stageguard_remediation_execution_uncertain {execution_uncertain}\n"
    )
    return metrics


def _single_query_value(query: dict[str, list[str]], name: str, *, required: bool = False) -> str | None:
    values = query.get(name)
    if values is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if len(values) != 1 or not values[0]:
        raise ValueError(f"{name} must be supplied exactly once")
    return values[0]


class StageGuardHandler(BaseHTTPRequestHandler):
    service: IncidentService
    identity_provider: IdentityProvider
    server_version = "StageGuard/0.11"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")

    def _send(self, status: int, payload: dict[str, Any], *, authenticate: bool = False) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        if authenticate:
            self.send_header("WWW-Authenticate", 'Bearer realm="stageguard"')
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, body_text: str, content_type: str, *, console_asset: bool = False) -> None:
        body = body_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        if console_asset:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, detail: str, *, authenticate: bool = False) -> None:
        self._send(status, {"error": code, "detail": detail}, authenticate=authenticate)

    def _identity(self) -> OperatorIdentity:
        return self.identity_provider.authenticate(self)

    def _serve_operator_console(self) -> bool:
        path = urlsplit(self.path).path
        assets = {
            "/console": (CONSOLE_HTML, "text/html; charset=utf-8"),
            "/assets/operator.css": (CONSOLE_CSS, "text/css; charset=utf-8"),
            "/assets/operator.js": (CONSOLE_JS, "text/javascript; charset=utf-8"),
        }
        asset = assets.get(path)
        if asset is None:
            return False
        try:
            self._identity()
        except AuthenticationError as exc:
            self._error(401, "unauthorized", str(exc), authenticate=True)
            return True
        self._send_text(200, asset[0], asset[1], console_asset=True)
        return True

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/healthz":
            self._send(200, {"ok": True})
            return
        if path == "/readyz":
            try:
                readiness = _service_readiness(self.service)
            except Exception:
                readiness = {
                    "ready": False,
                    "checks": {
                        "metric_activation": "failed",
                        "loki_activation": "failed",
                        "prometheus_mcp": "failed",
                        "loki_mcp": "failed",
                        "checkpoint": "failed",
                    },
                }
            self._send(200 if readiness["ready"] else 503, readiness)
            return
        if path == "/metrics":
            try:
                metrics = _service_metrics(self.service)
            except Exception:
                metrics = "# StageGuard metrics unavailable\n"
            self._send_text(200, metrics, "text/plain; version=0.0.4; charset=utf-8")
            return
        if self._serve_operator_console():
            return
        if path not in {"/v1/incident", "/v1/audit"}:
            self._error(404, "not_found", "unknown endpoint")
            return
        try:
            self._identity()
            if path == "/v1/audit":
                query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=4)
                unexpected = set(query) - {"incident_id", "after_sequence", "limit"}
                if unexpected:
                    raise ValueError(f"unsupported query fields: {', '.join(sorted(unexpected))}")
                incident_id = _single_query_value(query, "incident_id", required=True)
                after_raw = _single_query_value(query, "after_sequence")
                limit_raw = _single_query_value(query, "limit")
                try:
                    after_sequence = 0 if after_raw is None else int(after_raw)
                    limit = 50 if limit_raw is None else int(limit_raw)
                except ValueError as exc:
                    raise ValueError("after_sequence and limit must be integers") from exc
                timeline = self.service.audit_timeline(
                    incident_id=incident_id or "",
                    after_sequence=after_sequence,
                    limit=limit,
                )
                self._send(200, {"timeline": timeline})
                return
            self._send(200, _lifecycle_view(self.service))
        except AuthenticationError as exc:
            self._error(401, "unauthorized", str(exc), authenticate=True)
        except ValueError as exc:
            self._error(400, "invalid_request", str(exc))
        except RuntimeError as exc:
            self._error(409, "invalid_state", str(exc))
        except Exception:
            self._error(500, "internal_error", "request failed")

    def do_POST(self) -> None:  # noqa: N802
        try:
            identity = self._identity()
            payload = _read_json(self)

            if self.path == "/v1/investigate":
                _only(payload, set())
                snapshot = self.service.investigate(actor=identity.subject)
                self._send(200, {"incident": snapshot.to_dict()})
                return

            if self.path == "/v1/briefing":
                _only(payload, {"incident_id", "revision"})
                required = ("incident_id", "revision")
                if any(not isinstance(payload.get(name), str) for name in required):
                    raise ValueError("incident_id and revision are required strings")
                briefing = self.service.briefing(
                    incident_id=payload["incident_id"],
                    revision=payload["revision"],
                    actor=identity.subject,
                )
                self._send(200, {"briefing": briefing.to_dict(), "revision": payload["revision"]})
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

            if self.path == "/v1/checkpoint/reload":
                _only(payload, set())
                snapshot = self.service.reload_checkpoint_after_conflict()
                self._send(200, _lifecycle_view(self.service, snapshot))
                return

            if self.path == "/v1/execution/reconcile":
                _only(payload, set())
                reconcile = getattr(self.service, "reconcile_execution_uncertainty", None)
                if not callable(reconcile):
                    raise RuntimeError("execution reconciliation is not supported by this runtime")
                snapshot = reconcile(actor=identity.subject)
                self._send(200, _lifecycle_view(self.service, snapshot))
                return

            self._error(404, "not_found", "unknown endpoint")
        except AuthenticationError as exc:
            self._error(401, "unauthorized", str(exc), authenticate=True)
        except ValueError as exc:
            self._error(400, "invalid_request", str(exc))
        except RuntimeError as exc:
            self._error(409, "invalid_state", str(exc))
        except Exception:
            self._error(500, "internal_error", "request failed")


def make_server(
    service: IncidentService,
    host: str = "127.0.0.1",
    port: int = 9110,
    *,
    identity_provider: IdentityProvider | None = None,
) -> ThreadingHTTPServer:
    provider = identity_provider or LocalDevelopmentIdentityProvider()
    if not _is_loopback(host) and provider.is_development_only:
        raise ValueError("non-loopback bind requires an explicit production-capable identity provider")
    _get_readiness_probe(service)
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
    make_server(service, host, port, identity_provider=identity_provider).serve_forever()
