#!/usr/bin/env python3
"""Release-critical StageGuard local acceptance rehearsal.

This wrapper makes the existing local vertical slice deterministic by recreating
the compose stack and waiting until the exact Prometheus evidence used by
StageGuard is queryable before incident investigation. Interactive mode retains
a recording/operator pause; ``--non-interactive`` turns the same flow into an
automatable local acceptance check without adding GitHub Actions usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import demo_local  # noqa: E402

PROMETHEUS_QUERY_URL = "http://127.0.0.1:9090/api/v1/query"
PACKET_LOSS_QUERY = 'network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}'
DROP_RATE_QUERY = 'rate(video_frames_dropped_total{production_id="broadcast-alpha",feed_id="cam-3"}[2m])'
COMPOSE_DOWN_TIMEOUT_SECONDS = 45.0


class EvidenceGateError(RuntimeError):
    pass


def _prometheus_value(query: str, *, timeout: float = 3.0) -> float | None:
    url = PROMETHEUS_QUERY_URL + "?" + urllib.parse.urlencode({"query": query})
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise EvidenceGateError("Prometheus query did not return success")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "vector":
        raise EvidenceGateError("Prometheus query returned an unexpected result type")
    result = data.get("result")
    if not isinstance(result, list):
        raise EvidenceGateError("Prometheus query returned malformed vector data")
    if not result:
        return None
    if len(result) != 1:
        raise EvidenceGateError(f"bounded demo query returned {len(result)} series; expected exactly one")
    sample = result[0].get("value") if isinstance(result[0], dict) else None
    if not isinstance(sample, list) or len(sample) != 2:
        raise EvidenceGateError("Prometheus vector sample is malformed")
    try:
        return float(sample[1])
    except (TypeError, ValueError) as exc:
        raise EvidenceGateError("Prometheus sample value is not numeric") from exc


def _wait_for(label: str, query: str, predicate, *, timeout_seconds: float = 45.0) -> float:
    deadline = time.monotonic() + timeout_seconds
    last_value: float | None = None
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            last_value = _prometheus_value(query)
            last_error = None
            if last_value is not None and predicate(last_value):
                print(f"PASS: {label}: {last_value:.3f}")
                return last_value
        except Exception as exc:  # bounded operator diagnostic only
            last_error = type(exc).__name__
        time.sleep(1.0)
    detail = f"last_value={last_value!r}"
    if last_error:
        detail += f", last_error={last_error}"
    raise EvidenceGateError(f"timed out waiting for {label} ({detail})")


def _compose_down() -> None:
    try:
        result = subprocess.run(
            ["docker", "compose", "down", "--remove-orphans"],
            cwd=ROOT,
            text=True,
            check=False,
            timeout=COMPOSE_DOWN_TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvidenceGateError(
            f"docker compose down timed out after {COMPOSE_DOWN_TIMEOUT_SECONDS:.0f}s"
        ) from exc
    if result.returncode != 0:
        raise EvidenceGateError(f"docker compose down failed with exit code {result.returncode}")


def _recreate_compose_stack() -> None:
    # The demo compose file has no persistent volumes. Recreating its containers
    # clears old Prometheus samples so a previous rehearsal cannot contaminate
    # the next acceptance run. A failed teardown is fatal: continuing would make
    # the supposedly fresh evidence boundary untrustworthy.
    _compose_down()


def _confirm_fault_injection(*, non_interactive: bool) -> None:
    if non_interactive:
        print("[release] Non-interactive mode: injecting deterministic fault immediately after baseline verification.")
        return
    input("\nPress ENTER when ready to inject the deterministic uplink-b fault... ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start a clean StageGuard local stack and gate on real Prometheus evidence."
    )
    parser.add_argument("--gemini", action="store_true", help="enable the already-configured Vertex AI Gemini briefing")
    parser.add_argument("--open", action="store_true", help="open StageGuard and Grafana in the default browser")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="skip the operator/recording pause and inject the deterministic fault as soon as baseline evidence is verified",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="stop the local compose stack on exit (success or failure); useful for unattended acceptance runs",
    )
    args = parser.parse_args(argv)

    stack_owned = False
    exit_code = 1
    try:
        if demo_local._api_running():
            raise EvidenceGateError("StageGuard API is already running; run 'python scripts/demo_local.py stop' first")

        print("[release] Recreating local compose stack to remove stale telemetry...")
        _recreate_compose_stack()
        # From this point the rehearsal owns the local compose lifecycle. Mark it
        # before startup so --cleanup also handles partially-created containers
        # when demo_local.up() fails midway through startup.
        stack_owned = True
        demo_local.up(fresh=True, enable_gemini=args.gemini, open_browser=args.open)

        print("[release] Waiting for the healthy baseline used by the bounded investigator...")
        healthy_loss = _wait_for("healthy uplink-b packet loss < 1%", PACKET_LOSS_QUERY, lambda value: value < 1.0)
        healthy_drop = _wait_for("healthy cam-3 dropped-frame rate < 1/s", DROP_RATE_QUERY, lambda value: value < 1.0)

        print("\nHEALTHY BASELINE VERIFIED")
        print(json.dumps({"packet_loss_percent": healthy_loss, "cam3_drop_rate": healthy_drop}, indent=2))
        _confirm_fault_injection(non_interactive=args.non_interactive)

        demo_local.inject_fault(settle_seconds=0)
        print("[release] Waiting until the exact incident evidence is queryable in Prometheus...")
        fault_loss = _wait_for("faulted uplink-b packet loss > 5%", PACKET_LOSS_QUERY, lambda value: value > 5.0)
        fault_drop = _wait_for("faulted cam-3 dropped-frame rate > 1/s", DROP_RATE_QUERY, lambda value: value > 1.0)

        print("\nINCIDENT EVIDENCE READY — INVESTIGATION MAY START")
        print(json.dumps({"packet_loss_percent": fault_loss, "cam3_drop_rate": fault_drop}, indent=2))
        print("The real Grafana MCP smoke query already passed during startup.")
        print("Next: Investigate -> optional Gemini briefing -> approve exact revision -> Execute -> wait for recovered.")
        exit_code = 0
    except (EvidenceGateError, demo_local.DemoError, subprocess.CalledProcessError, OSError) as exc:
        print(f"RELEASE DEMO ERROR: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        if args.cleanup and stack_owned:
            print("[release] Cleaning up local compose stack...")
            try:
                _compose_down()
            except (EvidenceGateError, OSError) as exc:
                print(f"RELEASE CLEANUP ERROR: {exc}", file=sys.stderr)
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
