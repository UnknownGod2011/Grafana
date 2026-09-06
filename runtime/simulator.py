#!/usr/bin/env python3
"""Deterministic StageGuard broadcast telemetry simulator.

Zero third-party dependencies. Exposes Prometheus text metrics and a tiny
control API so the broadcast-alpha incident can be replayed locally.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict

PRODUCTION_ID = "broadcast-alpha"
FEEDS = ("cam-1", "cam-2", "cam-3")
ROUTES = {"cam-1": "uplink-a", "cam-2": "uplink-a", "cam-3": "uplink-b"}


class SimulationState:
    def __init__(self, start_faulted: bool = False) -> None:
        self._lock = threading.Lock()
        self.faulted = start_faulted
        self.frames_dropped: Dict[str, float] = {feed: 0.0 for feed in FEEDS}
        self.last_tick = time.monotonic()

    def tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            elapsed = max(0.0, now - self.last_tick)
            self.last_tick = now
            if self.faulted:
                self.frames_dropped["cam-3"] += 8.0 * elapsed

    def set_fault(self, enabled: bool) -> None:
        self.tick()
        with self._lock:
            self.faulted = enabled

    def reset(self) -> None:
        with self._lock:
            self.faulted = False
            self.frames_dropped = {feed: 0.0 for feed in FEEDS}
            self.last_tick = time.monotonic()

    def snapshot(self) -> dict:
        self.tick()
        with self._lock:
            return {
                "production_id": PRODUCTION_ID,
                "faulted": self.faulted,
                "fault": "uplink-b packet loss" if self.faulted else None,
                "routes": dict(ROUTES),
                "frames_dropped": dict(self.frames_dropped),
            }

    def prometheus_text(self) -> str:
        snap = self.snapshot()
        faulted = bool(snap["faulted"])
        dropped = snap["frames_dropped"]

        lines = [
            "# HELP video_frames_dropped_total Total dropped video frames.",
            "# TYPE video_frames_dropped_total counter",
        ]
        for feed in FEEDS:
            lines.append(
                f'video_frames_dropped_total{{production_id="{PRODUCTION_ID}",feed_id="{feed}"}} '
                f'{dropped[feed]:.3f}'
            )

        lines += [
            "# HELP encoder_cpu_percent Encoder CPU utilization percent.",
            "# TYPE encoder_cpu_percent gauge",
        ]
        cpu = {"cam-1": 36.0, "cam-2": 39.0, "cam-3": 41.0}
        for feed in FEEDS:
            lines.append(
                f'encoder_cpu_percent{{production_id="{PRODUCTION_ID}",feed_id="{feed}"}} {cpu[feed]:.1f}'
            )

        lines += [
            "# HELP encoder_gpu_percent Encoder GPU utilization percent.",
            "# TYPE encoder_gpu_percent gauge",
        ]
        gpu = {"cam-1": 31.0, "cam-2": 34.0, "cam-3": 37.0}
        for feed in FEEDS:
            lines.append(
                f'encoder_gpu_percent{{production_id="{PRODUCTION_ID}",feed_id="{feed}"}} {gpu[feed]:.1f}'
            )

        lines += [
            "# HELP network_packet_loss_percent Packet loss percentage by uplink.",
            "# TYPE network_packet_loss_percent gauge",
            f'network_packet_loss_percent{{production_id="{PRODUCTION_ID}",uplink="uplink-a"}} 0.2',
            f'network_packet_loss_percent{{production_id="{PRODUCTION_ID}",uplink="uplink-b"}} '
            f'{"18.0" if faulted else "0.3"}',
            "# HELP output_bitrate_mbps Program output bitrate in Mbps.",
            "# TYPE output_bitrate_mbps gauge",
            f'output_bitrate_mbps{{production_id="{PRODUCTION_ID}"}} {"6.4" if faulted else "8.0"}',
            "# HELP stageguard_scenario_fault_active Whether the seeded incident is active.",
            "# TYPE stageguard_scenario_fault_active gauge",
            f'stageguard_scenario_fault_active{{production_id="{PRODUCTION_ID}",scenario="uplink-b-packet-loss"}} '
            f'{"1" if faulted else "0"}',
        ]
        return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    state = SimulationState(
        start_faulted=os.getenv("STAGEGUARD_SCENARIO", "faulted").lower() == "faulted"
    )

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/metrics":
            body = self.state.prometheus_text().encode()
            self._send(200, body, "text/plain; version=0.0.4; charset=utf-8")
            return
        if self.path == "/healthz":
            self._send(200, b'{"status":"ok"}\n', "application/json")
            return
        if self.path == "/state":
            body = (json.dumps(self.state.snapshot(), sort_keys=True) + "\n").encode()
            self._send(200, body, "application/json")
            return
        self._send(404, b'{"error":"not_found"}\n', "application/json")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/scenario/fault":
            self.state.set_fault(True)
        elif self.path == "/scenario/recover":
            self.state.set_fault(False)
        elif self.path == "/scenario/reset":
            self.state.reset()
        else:
            self._send(404, b'{"error":"not_found"}\n', "application/json")
            return
        body = (json.dumps(self.state.snapshot(), sort_keys=True) + "\n").encode()
        self._send(200, body, "application/json")

    def log_message(self, fmt: str, *args: object) -> None:
        if os.getenv("STAGEGUARD_HTTP_LOG", "0") == "1":
            super().log_message(fmt, *args)


def main() -> None:
    host = os.getenv("STAGEGUARD_HOST", "0.0.0.0")
    port = int(os.getenv("STAGEGUARD_PORT", "9108"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(
        f"StageGuard simulator listening on http://{host}:{port} "
        f"(production={PRODUCTION_ID}, faulted={Handler.state.faulted})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
