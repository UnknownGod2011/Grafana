#!/usr/bin/env python3
"""One-command local StageGuard demo orchestration."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
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
    "cockpit": "http://127.0.0.1:9110/console", "api_health": "http://127.0.0.1:9110/healthz",
    "simulator_health": "http://127.0.0.1:9108/healthz", "simulator_state": "http://127.0.0.1:9108/state",
    "grafana": "http://127.0.0.1:3000", "grafana_health": "http://127.0.0.1:3000/api/health",
    "prometheus": "http://127.0.0.1:9090", "prometheus_ready": "http://127.0.0.1:9090/-/ready",
}

class DemoError(RuntimeError): pass

def _run(command, *, capture=False, env=None):
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=capture, check=True)

def _docker(*args, capture=False): return _run(["docker", "compose", *args], capture=capture)

def _request_json(url, *, method="GET", timeout=3.0):
    data = b"{}" if method != "GET" else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"} if data is not None else {}, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8").strip()
        if response.status >= 400: raise DemoError(f"{url} returned HTTP {response.status}")
        if not raw: return {}
        value = json.loads(raw)
        if not isinstance(value, dict): raise DemoError(f"{url} returned a non-object JSON response")
        return value

def _url_ok(url, *, timeout=2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response: return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError): return False

def _wait_url(url, *, timeout_seconds, label):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _url_ok(url): return
        time.sleep(1)
    raise DemoError(f"{label} did not become ready within {timeout_seconds:.0f}s ({url})")

def _ensure_state_dir(): STATE_DIR.mkdir(parents=True, exist_ok=True)

def _fresh_state():
    _ensure_state_dir()
    for path in (PID_PATH, API_LOG, CHECKPOINT_PATH, AUDIT_PATH, HMAC_KEY_PATH, REPORT_PATH): path.unlink(missing_ok=True)

def _ensure_hmac_key():
    _ensure_state_dir()
    if HMAC_KEY_PATH.exists():
        value = HMAC_KEY_PATH.read_text(encoding="utf-8").strip()
        if len(value.encode()) >= 32: return value
        raise DemoError("existing demo checkpoint HMAC key is invalid; run with --fresh")
    value = secrets.token_hex(32)
    fd = os.open(HMAC_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (value+"\n").encode()); os.fsync(fd)
    finally: os.close(fd)
    return value

def _api_running(): return _url_ok(URLS["api_health"])

def _reap_spawn_failure(process):
    """Stop only the exact child created by this invocation and clear ownership metadata."""
    try:
        if process.poll() is None:
            try: process.terminate()
            except ProcessLookupError: pass
            try:
                process.wait(timeout=5); return
            except subprocess.TimeoutExpired: pass
            try: process.kill()
            except ProcessLookupError: pass
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired as exc:
                raise DemoError("StageGuard API child did not exit after terminate/kill; manual process inspection is required") from exc
        else:
            process.wait(timeout=0)
    finally:
        PID_PATH.unlink(missing_ok=True)

def _spawn_api(*, enable_gemini):
    if _api_running(): raise DemoError("StageGuard API already appears to be running on port 9110")
    key = _ensure_hmac_key(); env = os.environ.copy(); env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = key; env["PYTHONUNBUFFERED"] = "1"
    command = [sys.executable, str(RUNTIME/"bootstrap.py"), "--telemetry-config", str(RUNTIME/"telemetry.example.json"), "--audit-log", str(AUDIT_PATH), "--checkpoint-backend", "signed-json", "--checkpoint-path", str(CHECKPOINT_PATH), "--audit-anchor-interval", "32", "--audit-integrity-policy", "allow_unbound_legacy", "--identity-mode", "local", "--host", "127.0.0.1", "--port", "9110"]
    if enable_gemini: command.append("--enable-gemini")
    log_handle = API_LOG.open("ab", buffering=0)
    kwargs = {"cwd":ROOT, "env":env, "stdout":log_handle, "stderr":subprocess.STDOUT}
    if os.name == "nt": kwargs["creationflags"] = getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) | getattr(subprocess,"DETACHED_PROCESS",0)
    else: kwargs["start_new_session"] = True
    try: process = subprocess.Popen(command, **kwargs)
    finally: log_handle.close()
    PID_PATH.write_text(str(process.pid)+"\n", encoding="utf-8")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _api_running(): return process
        code = process.poll()
        if code is not None:
            tail = API_LOG.read_text(encoding="utf-8", errors="replace")[-4000:] if API_LOG.exists() else ""
            _reap_spawn_failure(process)
            raise DemoError(f"StageGuard API exited with code {code}.\n{tail}")
        time.sleep(.5)
    _reap_spawn_failure(process)
    raise DemoError(f"StageGuard API did not become healthy; inspect {API_LOG}")

def _pid_command(pid):
    """Return a bounded best-effort command line for *pid*, or None if unverifiable."""
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if proc_cmdline.exists():
        try:
            raw = proc_cmdline.read_bytes()
            if raw: return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        except OSError: pass
    try:
        if os.name == "nt":
            command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"]
        else:
            command = ["ps", "-p", str(pid), "-o", "command="]
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=2)
        value = result.stdout.strip()
        return value if result.returncode == 0 and value else None
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

def _pid_matches_stageguard_api(pid):
    """Structurally prove persisted-PID ownership before allowing a signal."""
    command = _pid_command(pid)
    if not command: return False
    try:
        argv = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return False
    if not argv: return False

    expected_bootstrap = os.path.normcase(os.path.abspath(str(RUNTIME / "bootstrap.py")))
    script_indexes = []
    for index, token in enumerate(argv):
        candidate = token.strip('"') if os.name == "nt" else token
        if not candidate.lower().endswith("bootstrap.py"): continue
        candidate_path = os.path.normcase(os.path.abspath(candidate))
        if candidate_path == expected_bootstrap: script_indexes.append(index)
    if len(script_indexes) != 1: return False

    def option_values(name):
        values = []
        for index, token in enumerate(argv):
            clean = token.strip('"') if os.name == "nt" else token
            if clean == name:
                if index + 1 >= len(argv): return None
                value = argv[index + 1]
                values.append(value.strip('"') if os.name == "nt" else value)
            elif clean.startswith(name + "="):
                values.append(clean[len(name) + 1:])
        return values

    identity_values = option_values("--identity-mode")
    port_values = option_values("--port")
    return identity_values == ["local"] and port_values == ["9110"]

def _stop_api():
    if not PID_PATH.exists(): return
    try: pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        if _api_running(): raise DemoError("invalid StageGuard API PID metadata while API is reachable; refusing unsafe process termination")
        PID_PATH.unlink(missing_ok=True); return
    if not _api_running():
        PID_PATH.unlink(missing_ok=True); return
    if not _pid_matches_stageguard_api(pid):
        raise DemoError(f"PID {pid} cannot be verified as the StageGuard local API; refusing to signal it")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except (PermissionError, OSError) as exc:
        raise DemoError(f"could not terminate verified StageGuard API PID {pid}: {exc}") from exc
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and _api_running(): time.sleep(.25)
    if _api_running():
        raise DemoError(f"verified StageGuard API PID {pid} did not stop after SIGTERM; ownership metadata retained")
    PID_PATH.unlink(missing_ok=True)

def _check_docker():
    try: _run(["docker","compose","version"], capture=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc: raise DemoError("Docker with the Compose plugin is required for the local demo") from exc

def _bootstrap_stack():
    print("[1/5] Starting simulator + Prometheus + Grafana..."); _docker("up","-d","--build","simulator","prometheus","grafana")
    _wait_url(URLS["simulator_health"], timeout_seconds=90, label="simulator"); _wait_url(URLS["prometheus_ready"], timeout_seconds=90, label="Prometheus"); _wait_url(URLS["grafana_health"], timeout_seconds=90, label="Grafana")
    _request_json("http://127.0.0.1:9108/scenario/reset", method="POST"); time.sleep(5)

def _bootstrap_mcp():
    print("[2/5] Creating/reusing local read-only Grafana MCP credential..."); _run([sys.executable,str(RUNTIME/"bootstrap_grafana.py")])
    print("[3/5] Proving official Grafana MCP -> Grafana -> Prometheus..."); result=_run([sys.executable,str(RUNTIME/"mcp_smoke.py")],capture=True); output=result.stdout.strip()
    if "PASS: official Grafana MCP executed a read-only Prometheus query through Grafana." not in output: raise DemoError("Grafana MCP smoke command completed without the expected PASS marker")
    return output

def _write_report(*, mcp_smoke, gemini_enabled):
    report={"generated_unix":int(time.time()),"mode":"local-demo","gemini_enabled":bool(gemini_enabled),"checks":{"simulator":_url_ok(URLS["simulator_health"]),"prometheus":_url_ok(URLS["prometheus_ready"]),"grafana":_url_ok(URLS["grafana_health"]),"grafana_mcp_read_only_query":"PASS:" in mcp_smoke,"stageguard_api":_api_running()},"urls":{"cockpit":URLS["cockpit"],"grafana":URLS["grafana"],"prometheus":URLS["prometheus"],"simulator_state":URLS["simulator_state"]}}
    REPORT_PATH.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return report

def up(*, fresh, enable_gemini, open_browser):
    _check_docker()
    if fresh:
        if _api_running(): raise DemoError("refusing --fresh while the StageGuard API is running; stop the demo first")
        _fresh_state()
    _ensure_state_dir(); _bootstrap_stack(); mcp_smoke=_bootstrap_mcp(); print("[4/5] Starting StageGuard operator cockpit..."); _spawn_api(enable_gemini=enable_gemini); report=_write_report(mcp_smoke=mcp_smoke,gemini_enabled=enable_gemini)
    print("[5/5] Demo environment ready."); print(json.dumps(report,indent=2,sort_keys=True)); print(f"\nCockpit:   {URLS['cockpit']}"); print(f"Grafana:   {URLS['grafana']}  (admin / stageguard-local-only)"); print(f"Simulator: {URLS['simulator_state']}"); print(f"API log:   {API_LOG.relative_to(ROOT)}"); print(f"Report:    {REPORT_PATH.relative_to(ROOT)}")
    if open_browser: webbrowser.open(URLS["cockpit"]); webbrowser.open(URLS["grafana"])
    return report

def inject_fault(*, settle_seconds=6.0):
    if not _url_ok(URLS["simulator_health"]): raise DemoError("simulator is not running; start the demo first")
    _request_json("http://127.0.0.1:9108/scenario/fault",method="POST"); print("Injected deterministic uplink-b packet-loss fault.")
    if settle_seconds>0: print(f"Waiting {settle_seconds:.0f}s for Prometheus to collect failure samples..."); time.sleep(settle_seconds)
    current=_request_json(URLS["simulator_state"]); print(json.dumps(current,indent=2,sort_keys=True)); return current

def reset_scenario(): state=_request_json("http://127.0.0.1:9108/scenario/reset",method="POST"); print(json.dumps(state,indent=2,sort_keys=True)); return state

def status():
    result={"checks":{"stageguard_api":_api_running(),"simulator":_url_ok(URLS["simulator_health"]),"prometheus":_url_ok(URLS["prometheus_ready"]),"grafana":_url_ok(URLS["grafana_health"])},"simulator":None,"urls":URLS}
    if result["checks"]["simulator"]:
        try: result["simulator"]=_request_json(URLS["simulator_state"])
        except Exception: result["simulator"]={"status":"unavailable"}
    print(json.dumps(result,indent=2,sort_keys=True)); return result

def stop(*, keep_stack):
    print("Stopping StageGuard API..."); _stop_api()
    if not keep_stack:
        print("Stopping local Docker stack...")
        try: _docker("down")
        except (FileNotFoundError,subprocess.CalledProcessError): pass
    print("Stopped.")

def interactive_demo(*, enable_gemini, open_browser):
    up(fresh=True,enable_gemini=enable_gemini,open_browser=open_browser); print("\n=== RECORDING FLOW ==="); print("1. Show the healthy cockpit + Grafana for ~10 seconds."); input("2. Press ENTER when recording is ready to inject uplink-b failure... "); inject_fault(settle_seconds=6); print("\n3. In the cockpit click Investigate."); print("4. Request the Gemini briefing after diagnosis." if enable_gemini else "4. Approve the exact displayed evidence revision, then Execute."); print("5. Approve the exact displayed evidence revision, then Execute." if enable_gemini else "6. Keep Grafana visible while StageGuard verifies recovery from telemetry."); print("6. Keep Grafana visible while StageGuard verifies recovery from telemetry."); print("\nThe environment will remain running after this command exits."); print(f"Stop later with: {sys.executable} scripts/demo_local.py stop")

def main(argv=None):
    parser=argparse.ArgumentParser(description="Run the local StageGuard demonstration."); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("up",help="start a healthy demo environment"); p.add_argument("--fresh",action="store_true"); p.add_argument("--gemini",action="store_true"); p.add_argument("--open",action="store_true")
    p=sub.add_parser("demo",help="one-command interactive recording flow"); p.add_argument("--gemini",action="store_true"); p.add_argument("--open",action="store_true")
    sub.add_parser("fault"); sub.add_parser("reset"); sub.add_parser("status"); p=sub.add_parser("stop"); p.add_argument("--keep-stack",action="store_true")
    args=parser.parse_args(argv)
    try:
        if args.command=="up": up(fresh=args.fresh,enable_gemini=args.gemini,open_browser=args.open)
        elif args.command=="demo": interactive_demo(enable_gemini=args.gemini,open_browser=args.open)
        elif args.command=="fault": inject_fault()
        elif args.command=="reset": reset_scenario()
        elif args.command=="status": status()
        elif args.command=="stop": stop(keep_stack=args.keep_stack)
        return 0
    except (DemoError,subprocess.CalledProcessError,urllib.error.URLError,OSError) as exc: print(f"DEMO ERROR: {exc}",file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())