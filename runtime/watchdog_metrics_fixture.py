#!/usr/bin/env python3
"""Credential-free StageGuard watchdog metrics fixture for local Grafana rehearsal.

This process is deliberately NOT a remediation simulator. It exposes only the
four bounded watchdog series consumed by the source-controlled runtime-safety
dashboard and alerts. A tiny local-only control surface lets acceptance tests
move between idle, active, and overdue remediation states and independently
interrupt/resume metrics delivery.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


_STATES = {
    "idle": {"active": 0, "age": 0.0, "maximum": 60.0, "exceeded": 0},
    "active": {"active": 1, "age": 12.0, "maximum": 60.0, "exceeded": 0},
    "overdue": {"active": 1, "age": 75.0, "maximum": 60.0, "exceeded": 1},
}


class WatchdogFixtureState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._name = "idle"
        self._telemetry_available = True

    def set(self, name: str) -> None:
        if name not in _STATES:
            raise ValueError("unknown watchdog fixture state")
        with self._lock:
            self._name = name

    def set_telemetry_available(self, available: bool) -> None:
        if not isinstance(available, bool):
            raise TypeError("telemetry availability must be boolean")
        with self._lock:
            self._telemetry_available = available

    def snapshot(self) -> tuple[str, dict[str, float | int], bool]:
        with self._lock:
            name = self._name
            telemetry_available = self._telemetry_available
        return name, dict(_STATES[name]), telemetry_available

    def prometheus_metrics(self) -> str:
        _name, state, telemetry_available = self.snapshot()
        if not telemetry_available:
            raise RuntimeError("watchdog telemetry intentionally unavailable")
        return (
            "# HELP stageguard_remediation_execution_active Whether an approved remediation/recovery operation is currently active.\n"
            "# TYPE stageguard_remediation_execution_active gauge\n"
            f"stageguard_remediation_execution_active {state['active']}\n"
            "# HELP stageguard_remediation_execution_age_seconds Monotonic age in seconds of the active remediation/recovery operation.\n"
            "# TYPE stageguard_remediation_execution_age_seconds gauge\n"
            f"stageguard_remediation_execution_age_seconds {state['age']}\n"
            "# HELP stageguard_remediation_execution_max_seconds Configured maximum remediation/recovery execution window in seconds.\n"
            "# TYPE stageguard_remediation_execution_max_seconds gauge\n"
            f"stageguard_remediation_execution_max_seconds {state['maximum']}\n"
            "# HELP stageguard_remediation_execution_deadline_exceeded Whether the active remediation/recovery operation exceeded its configured window.\n"
            "# TYPE stageguard_remediation_execution_deadline_exceeded gauge\n"
            f"stageguard_remediation_execution_deadline_exceeded {state['exceeded']}\n"
        )


class WatchdogFixtureHandler(BaseHTTPRequestHandler):
    state: WatchdogFixtureState
    server_version = "StageGuardWatchdogFixture/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            body = b'{"ok":true}'
            self._send(200, body, "application/json")
            return
        if self.path == "/state":
            name, state, telemetry_available = self.state.snapshot()
            body = json.dumps(
                {"state": name, "telemetry_available": telemetry_available, **state},
                separators=(",", ":"),
            ).encode("utf-8")
            self._send(200, body, "application/json")
            return
        if self.path == "/metrics":
            try:
                metrics = self.state.prometheus_metrics()
            except RuntimeError:
                self._send(503, b"telemetry unavailable\n", "text/plain; charset=utf-8")
                return
            body = metrics.encode("utf-8")
            self._send(200, body, "text/plain; version=0.0.4; charset=utf-8")
            return
        self._send(404, b"not found\n", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        scenario_prefix = "/scenario/"
        if self.path.startswith(scenario_prefix):
            name = self.path[len(scenario_prefix):]
            try:
                self.state.set(name)
            except ValueError:
                self._send(404, b"unknown state\n", "text/plain; charset=utf-8")
                return
            body = json.dumps({"state": name}, separators=(",", ":")).encode("utf-8")
            self._send(200, body, "application/json")
            return

        telemetry_prefix = "/telemetry/"
        if self.path.startswith(telemetry_prefix):
            mode = self.path[len(telemetry_prefix):]
            if mode not in {"online", "offline"}:
                self._send(404, b"unknown telemetry mode\n", "text/plain; charset=utf-8")
                return
            available = mode == "online"
            self.state.set_telemetry_available(available)
            body = json.dumps(
                {"telemetry_available": available}, separators=(",", ":")
            ).encode("utf-8")
            self._send(200, body, "application/json")
            return

        self._send(404, b"not found\n", "text/plain; charset=utf-8")


def make_server(host: str = "0.0.0.0", port: int = 9111) -> ThreadingHTTPServer:
    state = WatchdogFixtureState()
    handler = type("ConfiguredWatchdogFixtureHandler", (WatchdogFixtureHandler,), {"state": state})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    server = make_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
