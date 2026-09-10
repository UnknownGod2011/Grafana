#!/usr/bin/env python3
"""Private scrape bridge for an authenticated StageGuard Cloud Run service.

Prometheus scrapes this tiny bridge on a trusted local/private network. The
bridge obtains a short-lived Google-signed ID token for the configured Cloud
Run audience and forwards only GET /metrics. It never forwards caller headers,
never accepts an arbitrary upstream path, and never logs tokens or upstream
error bodies.

The production dependency set already includes ``google-auth``. Tests inject a
token supplier and opener, so they remain credential-free.
"""
from __future__ import annotations

import argparse
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


class BridgeConfigurationError(ValueError):
    """Raised when the bridge would expose or target an unsafe endpoint."""


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


def google_id_token(audience: str) -> str:
    """Fetch a short-lived ID token through Application Default Credentials."""
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token
    except ImportError as exc:  # pragma: no cover - exercised by deployment packaging
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
        opener: Callable[..., object] = urllib.request.urlopen,
    ) -> None:
        self.metrics_url, default_audience = normalize_target(target)
        self.audience = normalize_audience(audience) if audience else default_audience
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
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/plain",
                "User-Agent": "stageguard-metrics-bridge/1",
            },
            method="GET",
        )
        with self._opener(request, timeout=self.timeout_seconds) as response:
            body = response.read(MAX_METRICS_BYTES + 1)
        if len(body) > MAX_METRICS_BYTES:
            raise RuntimeError("upstream metrics response exceeded the configured limit")
        return body


class MetricsBridgeHandler(BaseHTTPRequestHandler):
    client: CloudRunMetricsClient
    server_version = "StageGuardMetricsBridge/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            body = b'{"ok":true}'
            self._headers(200, "application/json", len(body))
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
            # Deliberately do not expose token, target URL, ADC details, provider
            # response bodies, or exception text to the scrape client.
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
) -> ThreadingHTTPServer:
    if not _is_loopback(host) and not allow_network_bind:
        raise BridgeConfigurationError("non-loopback metrics bridge bind requires --allow-network-bind")
    handler = type("ConfiguredMetricsBridgeHandler", (MetricsBridgeHandler,), {"client": client})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Authenticate Prometheus scrapes to StageGuard on Cloud Run")
    parser.add_argument("--target", default=os.environ.get("STAGEGUARD_METRICS_TARGET"))
    parser.add_argument("--audience", default=os.environ.get("STAGEGUARD_METRICS_AUDIENCE"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9112)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--allow-network-bind", action="store_true")
    args = parser.parse_args()
    if not args.target:
        parser.error("--target or STAGEGUARD_METRICS_TARGET is required")
    client = CloudRunMetricsClient(args.target, audience=args.audience, timeout_seconds=args.timeout_seconds)
    server = make_server(client, args.host, args.port, allow_network_bind=args.allow_network_bind)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
