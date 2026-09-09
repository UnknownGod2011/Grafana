#!/usr/bin/env python3
"""One-command local StageGuard demo orchestration.

Starts the deterministic broadcast simulator, Prometheus, Grafana, bootstraps a
short-lived read-only Grafana service account for the official MCP server,
proves the MCP query path, and starts the StageGuard operator cockpit.

No production credentials are created or used. All generated local state lives
under .stageguard/demo or runtime/.secrets, both gitignored.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
STATE_DIR = ROOT / ".stageguard" / "demo"
PID_PATH = STATE_DIR / "stageguard-api.pid"
API_LOG = STATE_DIR / "stageguard-api.log"
CHECKPOINT_PATH = STATE_DIR / "checkpoint.json"
AUDIT_PATH = STATE_DIR / "audit.jsonl"
HMAC_KEY_PATH = STATE_DIR / "checkpoint-hmac-key"
REPORT_PATH = STATE_DIR / "readiness.json"

URLS = {
    "cockpit": "http://127.0.0.1:9110/console",
    "api_health": "http://127.0.0.1:9110/healthz",
    "simulator_health": "http://127.0.0.1:9108/healthz",
    "simulator_state": "http://127.0.0.1:9108/state",
    "grafana": "http://127.0.0.1:3000",
    "grafana_health": "http://127.0.0.1:3000/api/health",
    "prometheus": "http://127.0.0.1:9090",
    "prometheus_ready": "http://127.0.0.1:9090/-/ready",
}


class DemoError(RuntimeError):
    pass


def _run(command: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=capture, check=True)


def _docker(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    return _run(["docker", "compose", *args], capture=capture)


def _request_json(url: str, *, method: str = "GET", timeout: float = 3.0) -> dict:
    data = b"{}" if method != "GET" else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8").strip()
        if response.status >= 400:
            raise DemoError(f"{url} returned HTTP {response.status}")
        if not raw:
            return {}
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise DemoError(f"{url} returned a non-object JSON response")
        return value


def _url_ok(url: str, *, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait_url(url: str, *, timeout_seconds: float, label: str) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _url_ok(url):
            return
        time.sleep(1)
    raise DemoError(f"{label} did not become ready within {timeout_seconds:.0f}s ({url})")


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _fresh_state() -> None:
    _ensure_state_dir()
    for path in (PID_PATH, API_LOG, CHECKPOINT_PATH, AUDIT_PATH, HMAC_KEY_PATH, REPORT_PATH):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _ensure_hmac_key() -> str:
    _ensure_state_dir()
    if HMAC_KEY_PATH.exists():
        value = HMAC_KEY_PATH.read_text(encoding="utf-8").strip()
        if len(value.encode("utf-8")) >= 32:
            return value
        raise DemoError("existing demo checkpoint HMAC key is invalid; run with --fresh")
    value = secrets.token_hex(32)
    fd = os.open(HMAC_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (value + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return value


def _api_running() -> bool:
    return _url_ok(URLS["api_health"])


def _spawn_api(*, enable_gemini: bool) -> subprocess.Popen:
    if _api_running():
        raise DemoError("StageGuard API already appears to be running on port 9110")
    key = _ensure_hmac_key()
    env = os.environ.copy()
    env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = key
    env["PYTHONUNBUFFERED"] = "1"
    command = [
        sys.executable,
        str(RUNTIME / "bootstrap.py"),
        "--telemetry-config", str(RUNTIME / "telemetry.example.json"),
        "--audit-log", str(AUDIT_PATH),
        "--checkpoint-backend", "signed-json",
        "--checkpoint-path", str(CHECKPOINT_PATH),
        "--audit-anchor-interval", "32",
        "--audit-integrity-policy", "allow_unbound_legacy",
        "--identity-mode", "local",
        "--host", "127.0.0.1",
        "--port", "9110",
    ]
    if enable_gemini:
        command.append("--enable-gemini")

    log_handle = API_LOG.open("ab", buffering=0)
    kwargs: dict = {
        "cwd": ROOT,
        "env": env,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **kwargs)
    finally:
        log_handle.close()
    PID_PATH.write_text(str(process.pid) + "\n", encoding="utf-8")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _api_running():
            return process
        code = process.poll()
        if code is not None:
            tail = API_LOG.read_text(encoding="utf-8", errors="replace")[-4000:] if API_LOG.exists() else ""
            raise DemoError(f"StageGuard API exited with code {code}.\n{tail}")
        time.sleep(0.5)
    raise DemoError(f"StageGuard API did not become healthy; inspect {API_LOG}")


def _stop_api() -> None:
    if not PID_PATH.exists():
        return
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_PATH.unlink(missing_ok=True)
        return
    # Never signal a stale/reused PID unless the expected local StageGuard HTTP
    # endpoint is currently alive.
    if _api_running():
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _api_running():
            time.sleep(0.25)
    PID_PATH.unlink(missing_ok=True)


def _check_docker() -> None:
    try:
        _run(["docker", "compose", "version"], capture=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise DemoError("Docker with the Compose plugin is required for the local demo") from exc


def _bootstrap_stack() -> None:
    print("[1/5] Starting simulator + Prometheus + Grafana...")
    _docker("up", "-d", "--build", "simulator", "prometheus", "grafana")
    _wait_url(URLS["simulator_health"], timeout_seconds=90, label="simulator")
    _wait_url(URLS["prometheus_ready"], timeout_seconds=90, label="Prometheus")
    _wait_url(URLS["grafana_health"], timeout_seconds=90, label="Grafana")
    # Begin healthy so the failure is visibly injected during the recording.
    _request_json("http://127.0.0.1:9108/scenario/reset", method="POST")
    time.sleep(5)


def _bootstrap_mcp() -> str:
    print("[2/5] Creating/reusing local read-only Grafana MCP credential...")
    _run([sys.executable, str(RUNTIME / "bootstrap_grafana.py")])
    print("[3/5] Proving official Grafana MCP -> Grafana -> Prometheus...")
    result = _run([sys.executable, str(RUNTIME / "mcp_smoke.py")], capture=True)
    output = result.stdout.strip()
    marker = "PASS: official Grafana MCP executed a read-only Prometheus query through Grafana."
    if marker not in output:
        raise DemoError("Grafana MCP smoke command completed without the expected PASS marker")
    return output


def _write_report(*, mcp_smoke: str, gemini_enabled: bool) -> dict:
    report = {
        "generated_unix": int(time.time()),
        "mode": "local-demo",
        "gemini_enabled": bool(gemini_enabled),
        "checks": {
            "simulator": _url_ok(URLS["simulator_health"]),
            "prometheus": _url_ok(URLS["prometheus_ready"]),
            "grafana": _url_ok(URLS["grafana_health"]),
            "grafana_mcp_read_only_query": "PASS:" in mcp_smoke,
            "stageguard_api": _api_running(),
        },
        "urls": {
            "cockpit": URLS["cockpit"],
            "grafana": URLS["grafana"],
            "prometheus": URLS["prometheus"],
            "simulator_state": URLS["simulator_state"],
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def up(*, fresh: bool, enable_gemini: bool, open_browser: bool) -> dict:
    _check_docker()
    if fresh:
        if _api_running():
            raise DemoError("refusing --fresh while the StageGuard API is running; stop the demo first")
        _fresh_state()
    _ensure_state_dir()
    _bootstrap_stack()
    mcp_smoke = _bootstrap_mcp()
    print("[4/5] Starting StageGuard operator cockpit...")
    _spawn_api(enable_gemini=enable_gemini)
    report = _write_report(mcp_smoke=mcp_smoke, gemini_enabled=enable_gemini)
    print("[5/5] Demo environment ready.")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"\nCockpit:   {URLS['cockpit']}")
    print(f"Grafana:   {URLS['grafana']}  (admin / stageguard-local-only)")
    print(f"Simulator: {URLS['simulator_state']}")
    print(f"API log:   {API_LOG.relative_to(ROOT)}")
    print(f"Report:    {REPORT_PATH.relative_to(ROOT)}")
    if open_browser:
        webbrowser.open(URLS["cockpit"])
        webbrowser.open(URLS["grafana"])
    return report


def inject_fault(*, settle_seconds: float = 6.0) -> dict:
    if not _url_ok(URLS["simulator_health"]):
        raise DemoError("simulator is not running; start the demo first")
    _request_json("http://127.0.0.1:9108/scenario/fault", method="POST")
    print("Injected deterministic uplink-b packet-loss fault.")
    if settle_seconds > 0:
        print(f"Waiting {settle_seconds:.0f}s for Prometheus to collect failure samples...")
        time.sleep(settle_seconds)
    current = _request_json(URLS["simulator_state"])
    print(json.dumps(current, indent=2, sort_keys=True))
    return current


def reset_scenario() -> dict:
    state = _request_json("http://127.0.0.1:9108/scenario/reset", method="POST")
    print(json.dumps(state, indent=2, sort_keys=True))
    return state


def status() -> dict:
    result = {
        "checks": {
            "stageguard_api": _api_running(),
            "simulator": _url_ok(URLS["simulator_health"]),
            "prometheus": _url_ok(URLS["prometheus_ready"]),
            "grafana": _url_ok(URLS["grafana_health"]),
        },
        "simulator": None,
        "urls": URLS,
    }
    if result["checks"]["simulator"]:
        try:
            result["simulator"] = _request_json(URLS["simulator_state"])
        except Exception:
            result["simulator"] = {"status": "unavailable"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def stop(*, keep_stack: bool) -> None:
    print("Stopping StageGuard API...")
    _stop_api()
    if not keep_stack:
        print("Stopping local Docker stack...")
        try:
            _docker("down")
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    print("Stopped.")


def interactive_demo(*, enable_gemini: bool, open_browser: bool) -> None:
    up(fresh=True, enable_gemini=enable_gemini, open_browser=open_browser)
    print("\n=== RECORDING FLOW ===")
    print("1. Show the healthy cockpit + Grafana for ~10 seconds.")
    input("2. Press ENTER when recording is ready to inject uplink-b failure... ")
    inject_fault(settle_seconds=6)
    print("\n3. In the cockpit click Investigate.")
    if enable_gemini:
        print("4. Request the Gemini briefing after diagnosis.")
        print("5. Approve the exact displayed evidence revision, then Execute.")
    else:
        print("4. Approve the exact displayed evidence revision, then Execute.")
    print("6. Keep Grafana visible while StageGuard verifies recovery from telemetry.")
    print("\nThe environment will remain running after this command exits.")
    print(f"Stop later with: {sys.executable} scripts/demo_local.py stop")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local StageGuard demonstration.")
    sub = parser.add_subparsers(dest="command", required=True)
    up_parser = sub.add_parser("up", help="start a healthy demo environment")
    up_parser.add_argument("--fresh", action="store_true", help="clear only .stageguard/demo state before start")
    up_parser.add_argument("--gemini", action="store_true", help="enable the configured Vertex AI Gemini commander")
    up_parser.add_argument("--open", action="store_true", help="open cockpit and Grafana in the default browser")
    demo_parser = sub.add_parser("demo", help="one-command interactive recording flow")
    demo_parser.add_argument("--gemini", action="store_true", help="enable the configured Vertex AI Gemini commander")
    demo_parser.add_argument("--open", action="store_true", help="open cockpit and Grafana in the default browser")
    sub.add_parser("fault", help="inject the deterministic uplink-b fault")
    sub.add_parser("reset", help="return the simulated broadcast to healthy state")
    sub.add_parser("status", help="print a bounded demo status report")
    stop_parser = sub.add_parser("stop", help="stop StageGuard and the local Docker stack")
    stop_parser.add_argument("--keep-stack", action="store_true", help="stop only the StageGuard API")
    args = parser.parse_args(argv)
    try:
        if args.command == "up":
            up(fresh=args.fresh, enable_gemini=args.gemini, open_browser=args.open)
        elif args.command == "demo":
            interactive_demo(enable_gemini=args.gemini, open_browser=args.open)
        elif args.command == "fault":
            inject_fault()
        elif args.command == "reset":
            reset_scenario()
        elif args.command == "status":
            status()
        elif args.command == "stop":
            stop(keep_stack=args.keep_stack)
        return 0
    except (DemoError, subprocess.CalledProcessError, urllib.error.URLError, OSError) as exc:
        print(f"DEMO ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
