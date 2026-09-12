#!/usr/bin/env python3
"""Private scrape bridge for an authenticated StageGuard Cloud Run service.

The bridge obtains a short-lived Google-signed ID token for the configured
Cloud Run audience and forwards only GET /metrics. It never forwards caller
headers, never accepts an arbitrary upstream path, never follows upstream
redirects, and never logs tokens or upstream error bodies.

An optional *inbound* bearer token can protect /readyz and /metrics when the
bridge is loopback-only. If the bridge binds beyond loopback (for example, so
Prometheus in Docker can scrape the host), inbound bearer authentication is
mandatory in addition to explicit network-bind opt-in. This token is
independent from the Google ID token: callers never receive or control the
upstream credential. /healthz remains process-only liveness and does not mint
an upstream token.

A successful upstream HTTP response is not sufficient evidence that the bridge
reached StageGuard. Every accepted payload must contain exactly one finite,
boolean-valued, label-free remediation-deadline sentinel and no additional
series in that sentinel metric family.
"""
from __future__ import annotations

import argparse
import hmac
import ipaddress
import math
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

MAX_METRICS_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 10.0
SAFETY_SENTINEL_METRIC = b"stageguard_remediation_execution_deadline_exceeded"


class BridgeConfigurationError(ValueError):
    """Raised when the bridge would expose or target an unsafe endpoint."""


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse every upstream redirect instead of replaying an identity token."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _open_without_redirects(request: urllib.request.Request, *, timeout: float):
    return urllib.request.build_opener(_RejectRedirectHandler()).open(request, timeout=timeout)


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalize_target(value: str) -> tuple[str, str]:
    """Return ``(metrics_url, default_audience)`` for one HTTPS service origin."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise BridgeConfigurationError("metrics target must be a non-empty trimmed URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        raise BridgeConfigurationError("metrics target must use https")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise BridgeConfigurationError("metrics target must be an HTTPS service origin without user info")
    if parsed.query or parsed.fragment:
        raise BridgeConfigurationError("metrics target must not contain a query or fragment")
    if parsed.path not in {"", "/"}:
        raise BridgeConfigurationError("metrics target must be a service origin, not an arbitrary path")
    authority = parsed.netloc
    origin = urlunsplit(("https", authority, "", "", ""))
    return f"{origin}/metrics", origin


def normalize_audience(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise BridgeConfigurationError("metrics audience must be a non-empty trimmed URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise BridgeConfigurationError("metrics audience must use https")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise BridgeConfigurationError("metrics audience must not contain user info, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise BridgeConfigurationError("metrics audience must be a service origin")
    return urlunsplit(("https", parsed.netloc, "", "", ""))


def normalize_bridge_bearer_token(value: str | None) -> str | None:
    """Validate an optional inbound scrape credential without logging it."""
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise BridgeConfigurationError("bridge bearer token must be a non-empty trimmed string")
    if "\r" in value or "\n" in value:
        raise BridgeConfigurationError("bridge bearer token must not contain line breaks")
    return value


def _is_sentinel_family_token(token: bytes) -> bool:
    return token == SAFETY_SENTINEL_METRIC or token.startswith(SAFETY_SENTINEL_METRIC + b"{")


def validate_stageguard_metrics(body: bytes) -> None:
    """Require one authoritative finite StageGuard deadline sentinel sample."""
    if not isinstance(body, bytes):
        raise RuntimeError("upstream metrics response was not bytes")
    samples: list[bytes] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(b"#"):
            continue
        fields = line.split()
        if not fields or not _is_sentinel_family_token(fields[0]):
            continue
        if fields[0] != SAFETY_SENTINEL_METRIC:
            raise RuntimeError("upstream StageGuard safety sentinel contained unauthorized labels")
        if len(fields) != 2:
            raise RuntimeError("upstream StageGuard safety sentinel was malformed")
        samples.append(fields[1])
    if len(samples) != 1:
        raise RuntimeError("upstream StageGuard safety sentinel was missing or ambiguous")
    try:
        value = float(samples[0].decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("upstream StageGuard safety sentinel was nonnumeric") from exc
    if not math.isfinite(value) or value not in {0.0, 1.0}:
        raise RuntimeError("upstream StageGuard safety sentinel was invalid")


def google_id_token(audience: str) -> str:
    """Fetch a short-lived ID token through Application Default Credentials."""
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("google-auth is required for Cloud Run metrics authentication") from exc
    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, audience)
    if not isinstance(token, str) or not token:
        raise RuntimeError("could not obtain an ID token")
    return token


class CloudRunMetricsClient:
    def __init__(
        self,
        target: str,
        *,
        audience: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        token_supplier: Callable[[str], str] = google_id_token,
        opener: Callable[..., object] = _open_without_redirects,
        allow_cross_origin_audience: bool = False,
    ) -> None:
        self.metrics_url, target_origin = normalize_target(target)
        self.audience = normalize_audience(audience) if audience else target_origin
        if not isinstance(allow_cross_origin_audience, bool):
            raise BridgeConfigurationError("allow_cross_origin_audience must be boolean")
        if self.audience != target_origin and not allow_cross_origin_audience:
            raise BridgeConfigurationError(
                "metrics audience differs from target origin; explicit cross-origin audience opt-in is required"
            )
        if isinstance(timeout_seconds, bool):
            raise BridgeConfigurationError("timeout must be finite and positive")
        try:
            timeout_value = float(timeout_seconds)
        except (TypeError, ValueError) as exc:
            raise BridgeConfigurationError("timeout must be finite and positive") from exc
        if not math.isfinite(timeout_value) or timeout_value <= 0:
            raise BridgeConfigurationError("timeout must be finite and positive")
        self.timeout_seconds = timeout_value
        self._token_supplier = token_supplier
        self._opener = opener

    def fetch(self) -> bytes:
        token = self._token_supplier(self.audience)
        if not isinstance(token, str) or not token:
            raise RuntimeError("could not obtain an ID token")
        request = urllib.request.Request(
            self.metrics_url,
            headers={"Accept": "text/plain", "User-Agent": "stageguard-metrics-bridge/1"},
            method="GET",
        )
        request.add_unredirected_header("Authorization", f"Bearer {token}")
        with self._opener(request, timeout=self.timeout_seconds) as response:
            body = response.read(MAX_METRICS_BYTES + 1)
        if len(body) > MAX_METRICS_BYTES:
            raise RuntimeError("upstream metrics response exceeded the configured limit")
        validate_stageguard_metrics(body)
        return body


class MetricsBridgeHandler(BaseHTTPRequestHandler):
    client: CloudRunMetricsClient
    bridge_bearer_token: str | None = None
    server_version = "StageGuardMetricsBridge/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int, *, authenticate: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if authenticate:
            self.send_header("WWW-Authenticate", 'Bearer realm="stageguard-metrics"')
        self.end_headers()

    def _authorized(self) -> bool:
        expected = self.bridge_bearer_token
        if expected is None:
            return True
        presented = self.headers.get("Authorization")
        if not isinstance(presented, str) or not presented.startswith("Bearer "):
            return False
        candidate = presented[len("Bearer ") :]
        return hmac.compare_digest(candidate, expected)

    def _require_authorization(self) -> bool:
        if self._authorized():
            return True
        body = b"unauthorized\n"
        self._headers(401, "text/plain; charset=utf-8", len(body), authenticate=True)
        self.wfile.write(body)
        return False

    def _upstream_ready(self) -> bool:
        try:
            self.client.fetch()
        except Exception:
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            body = b'{"ok":true}'
            self._headers(200, "application/json", len(body))
            self.wfile.write(body)
            return
        if self.path in {"/readyz", "/metrics"} and not self._require_authorization():
            return
        if self.path == "/readyz":
            if self._upstream_ready():
                body = b'{"ok":true,"upstream":"reachable"}'
                self._headers(200, "application/json", len(body))
            else:
                body = b'{"ok":false,"upstream":"unavailable"}'
                self._headers(503, "application/json", len(body))
            self.wfile.write(body)
            return
        if self.path != "/metrics":
            body = b"not found\n"
            self._headers(404, "text/plain; charset=utf-8", len(body))
            self.wfile.write(body)
            return
        try:
            body = self.client.fetch()
        except Exception:
            body = b"stageguard metrics upstream unavailable\n"
            self._headers(502, "text/plain; charset=utf-8", len(body))
            self.wfile.write(body)
            return
        self._headers(200, "text/plain; version=0.0.4; charset=utf-8", len(body))
        self.wfile.write(body)


def make_server(
    client: CloudRunMetricsClient,
    host: str = "127.0.0.1",
    port: int = 9112,
    *,
    allow_network_bind: bool = False,
    bearer_token: str | None = None,
) -> ThreadingHTTPServer:
    is_loopback = _is_loopback(host)
    if not is_loopback and not allow_network_bind:
        raise BridgeConfigurationError("non-loopback metrics bridge bind requires --allow-network-bind")
    normalized_token = normalize_bridge_bearer_token(bearer_token)
    if not is_loopback and normalized_token is None:
        raise BridgeConfigurationError("non-loopback metrics bridge bind requires inbound bearer authentication")
    handler = type(
        "ConfiguredMetricsBridgeHandler",
        (MetricsBridgeHandler,),
        {"client": client, "bridge_bearer_token": normalized_token},
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Authenticate Prometheus scrapes to StageGuard on Cloud Run")
    parser.add_argument("--target", default=os.environ.get("STAGEGUARD_METRICS_TARGET"))
    parser.add_argument("--audience", default=os.environ.get("STAGEGUARD_METRICS_AUDIENCE"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9112)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--allow-network-bind", action="store_true")
    parser.add_argument(
        "--bearer-token",
        default=os.environ.get("STAGEGUARD_BRIDGE_BEARER_TOKEN"),
        help="inbound bearer token protecting /readyz and /metrics; required for non-loopback binds",
    )
    parser.add_argument(
        "--allow-cross-origin-audience",
        action="store_true",
        help="allow an ID-token audience that differs from the metrics target origin",
    )
    args = parser.parse_args()
    if not args.target:
        parser.error("--target or STAGEGUARD_METRICS_TARGET is required")
    client = CloudRunMetricsClient(
        args.target,
        audience=args.audience,
        timeout_seconds=args.timeout_seconds,
        allow_cross_origin_audience=args.allow_cross_origin_audience,
    )
    server = make_server(
        client,
        args.host,
        args.port,
        allow_network_bind=args.allow_network_bind,
        bearer_token=args.bearer_token,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
