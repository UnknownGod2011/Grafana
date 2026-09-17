#!/usr/bin/env python3
"""Run StageGuard's dependency-light safety and Grafana/MCP regression gates.

Each gate is resolved to concrete, repository-local regular test files before
execution. This prevents a typo, layout change, or symlink from turning the
validator into either a false-green gate or an execution path outside the
intended test directory. Tests run in separate Python processes per file so
failures remain attributable without requiring runtime/tests to be a package.

The validation harness is itself a gate. Runtime activation validates the
configuration-to-runtime boundary before operator traffic is considered safe.
The incident-lifecycle gate covers the fail-closed path from investigation and
evidence availability through recovery rechecks. The operator API boundary gate
exercises authentication, request framing, protocol preflight, and HTTP surface
contracts before live deployment. The operator concurrency gate verifies that
long-running remediation keeps read-only observability responsive while
competing mutations fail closed.

Validation subprocesses are non-interactive, timeout-bounded, and receive a
credential-scrubbed environment. Python startup/import-path controls are
removed and user-site package loading is disabled. A test selected by multiple
gates executes once under its earliest owning gate; later gates report it as
already covered, avoiding repeated side effects and unnecessary runtime.
Subprocess launch failures are reported as validation failures rather than
escaping the harness with an unclassified traceback.

This runner does not start Docker, contact Grafana, trigger GitHub Actions, or
intentionally read credentials; live MCP smoke remains an explicit follow-up gate.
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "runtime" / "tests"
DEFAULT_FILE_TIMEOUT_SECONDS = 120.0
MAX_FILE_TIMEOUT_SECONDS = 3600.0

SENSITIVE_ENV_NAMES = frozenset({
    "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CREDENTIALS", "GOOGLE_CLOUD_KEYFILE_JSON",
    "CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONINSPECT", "PYTHONBREAKPOINT",
})
SENSITIVE_ENV_PREFIXES = ("GRAFANA_", "GEMINI_", "GOOGLE_API_", "STAGEGUARD_REMEDIATION_")
SENSITIVE_ENV_SUFFIXES = ("_TOKEN", "_API_KEY", "_PASSWORD", "_SECRET")
VALIDATION_ENV_OVERRIDES = {"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}

@dataclass(frozen=True)
class Gate:
    name: str
    patterns: tuple[str, ...]

GATES = (
    Gate("validation harness", ("test_stageguard_validation_runner.py",)),
    Gate("runtime activation", ("test_activation.py",)),
    Gate("operator API boundary", (
        "test_api.py", "test_api_auth_error_redaction.py", "test_api_protocol_preflight.py",
        "test_api_request_framing.py", "test_http_surface_contract.py", "test_identity.py",
    )),
    Gate("operator concurrency", ("test_api_concurrency.py", "test_api_execution_watchdog.py")),
    Gate("incident lifecycle", (
        "test_anchored_incident_runtime.py", "test_*evidence_unavailable*.py",
        "test_*recovery_recheck.py", "test_*transition_failure_authority.py",
    )),
    Gate("timeline disclosure", ("test_timeline*.py", "test_audit_timeline*.py")),
    Gate("public audit", ("test_*audit*.py",)),
    Gate("execution safety", ("test_*execution*.py",)),
    Gate("Grafana MCP", ("test_*mcp*.py",)),
)

def _safe_test_file(path: Path) -> bool:
    try:
        return path.parent.resolve(strict=True) == TESTS.resolve(strict=True) and not path.is_symlink() and path.is_file()
    except (OSError, RuntimeError):
        return False

def _files(gate: Gate) -> tuple[Path, ...]:
    selected: dict[str, Path] = {}
    for pattern in gate.patterns:
        for path in TESTS.glob(pattern):
            if _safe_test_file(path): selected[path.name] = path
    return tuple(selected[name] for name in sorted(selected))

def _execution_plan(selections: tuple[tuple[Gate, tuple[Path, ...]], ...]) -> tuple[tuple[Gate, tuple[Path, ...], tuple[Path, ...]], ...]:
    """Assign each selected test to its earliest gate while retaining overlap visibility."""
    seen: set[str] = set(); plan = []
    for gate, files in selections:
        runnable = tuple(path for path in files if path.name not in seen)
        covered = tuple(path for path in files if path.name in seen)
        seen.update(path.name for path in files); plan.append((gate, runnable, covered))
    return tuple(plan)

def _command(path: Path) -> list[str]:
    if not _safe_test_file(path): raise ValueError(f"unsafe validation test path: {path}")
    return [sys.executable, "-m", "unittest", "discover", "-s", str(TESTS), "-p", path.name]

def _is_sensitive_env_name(name: str) -> bool:
    upper = name.upper()
    return upper in SENSITIVE_ENV_NAMES or upper.startswith(SENSITIVE_ENV_PREFIXES) or upper.endswith(SENSITIVE_ENV_SUFFIXES)

def _validation_env(source: dict[str, str] | None = None) -> dict[str, str]:
    source_env = os.environ if source is None else source
    sanitized = {k: v for k, v in source_env.items() if not _is_sensitive_env_name(k)}
    sanitized.update(VALIDATION_ENV_OVERRIDES); return sanitized

def _positive_timeout(value: str) -> float:
    try: timeout = float(value)
    except ValueError as exc: raise argparse.ArgumentTypeError("timeout must be a number") from exc
    if not math.isfinite(timeout) or timeout <= 0: raise argparse.ArgumentTypeError("timeout must be a finite number greater than zero")
    if timeout > MAX_FILE_TIMEOUT_SECONDS: raise argparse.ArgumentTypeError(f"timeout must not exceed {MAX_FILE_TIMEOUT_SECONDS:g} seconds")
    return timeout

def _run_test_file(path: Path, *, timeout: float, env: dict[str, str]) -> int:
    completed = subprocess.run(_command(path), cwd=ROOT, check=False, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    return completed.returncode

def main() -> int:
    parser = argparse.ArgumentParser(description="Run dependency-light StageGuard safety/MCP regression gates.")
    parser.add_argument("--keep-going", action="store_true", help="run every selected test file even after a failure (default: fail fast)")
    parser.add_argument("--list", action="store_true", help="print the concrete tests selected by each gate without executing them")
    parser.add_argument("--file-timeout", type=_positive_timeout, default=DEFAULT_FILE_TIMEOUT_SECONDS, metavar="SECONDS", help=f"maximum runtime for each test file (default: {DEFAULT_FILE_TIMEOUT_SECONDS:g}s; maximum: {MAX_FILE_TIMEOUT_SECONDS:g}s)")
    args = parser.parse_args()
    if not TESTS.is_dir() or TESTS.is_symlink():
        print(f"error: safe test directory not found: {TESTS}", file=sys.stderr); return 2
    selections = tuple((gate, _files(gate)) for gate in GATES)
    empty = [gate.name for gate, files in selections if not files]
    if empty:
        print("error: validation gate matched no safe tests: " + ", ".join(empty), file=sys.stderr); return 2
    plan = _execution_plan(selections)
    if args.list:
        for gate, runnable, covered in plan:
            print(f"{gate.name} ({', '.join(gate.patterns)}):")
            for path in runnable: print(f"  {path.relative_to(ROOT)}")
            for path in covered: print(f"  {path.relative_to(ROOT)} [covered by earlier gate]")
        return 0
    failures: list[str] = []; validation_env = _validation_env()
    for gate, files, covered in plan:
        print(f"\n=== StageGuard gate: {gate.name} ({len(files)} files; {len(covered)} already covered) ===", flush=True)
        gate_failed = False
        for path in files:
            print(f"--- {path.name} ---", flush=True)
            try:
                failed = _run_test_file(path, timeout=args.file_timeout, env=validation_env) != 0
            except subprocess.TimeoutExpired:
                failed = True; print(f"TIMEOUT: {path.name} exceeded {args.file_timeout:g}s", file=sys.stderr)
            except OSError as exc:
                failed = True; print(f"LAUNCH ERROR: {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            if failed:
                gate_failed = True; failures.append(f"{gate.name}/{path.name}")
                if not args.keep_going: break
        if gate_failed and not args.keep_going: break
    if failures:
        print("\nFAILED tests: " + ", ".join(failures), file=sys.stderr); return 1
    print("\nAll selected StageGuard validation gates passed.")
    print("Live Docker/Grafana MCP smoke is intentionally not part of this runner."); return 0

if __name__ == "__main__": raise SystemExit(main())
