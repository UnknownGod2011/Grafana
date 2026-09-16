#!/usr/bin/env python3
"""Run StageGuard's dependency-light safety and Grafana/MCP regression gates.

Each gate is resolved to concrete test files before execution. This prevents a
typo or repository-layout change from turning an empty unittest discovery into
a false-green safety gate. Tests run in separate Python processes per file so
failures remain attributable without requiring runtime/tests to be a package.

The validation harness is itself a gate: changes to this script cannot receive
a green consolidated result without exercising its selection/command contracts.

This runner does not start Docker, contact Grafana, trigger GitHub Actions, or
read credentials; live MCP smoke remains an explicit follow-up gate.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "runtime" / "tests"


@dataclass(frozen=True)
class Gate:
    name: str
    patterns: tuple[str, ...]


GATES = (
    # Keep the runner's own contract in the consolidated gate. Otherwise a
    # regression in discovery/fail-closed behavior could still report green.
    Gate("validation harness", ("test_stageguard_validation_runner.py",)),
    # Timeline policy lives partly in audit-facing tests, so keep both naming
    # families in the same disclosure gate rather than relying on another gate
    # to exercise them incidentally.
    Gate("timeline disclosure", ("test_timeline*.py", "test_audit_timeline*.py")),
    Gate("public audit", ("test_*audit*.py",)),
    Gate("execution safety", ("test_*execution*.py",)),
    Gate("Grafana MCP", ("test_*mcp*.py",)),
)


def _files(gate: Gate) -> tuple[Path, ...]:
    selected: dict[str, Path] = {}
    for pattern in gate.patterns:
        for path in TESTS.glob(pattern):
            if path.is_file():
                selected[path.name] = path
    return tuple(selected[name] for name in sorted(selected))


def _command(path: Path) -> list[str]:
    # Discovery is intentionally scoped to one concrete file. Running from
    # ROOT keeps runtime imports available without making runtime/tests a
    # package or depending on unittest's top-level-directory inference.
    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(TESTS),
        "-p",
        path.name,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dependency-light StageGuard safety/MCP regression gates."
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="run every selected test file even after a failure (default: fail fast)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the concrete tests selected by each gate without executing them",
    )
    args = parser.parse_args()

    if not TESTS.is_dir():
        print(f"error: test directory not found: {TESTS}", file=sys.stderr)
        return 2

    selections = tuple((gate, _files(gate)) for gate in GATES)
    empty = [gate.name for gate, files in selections if not files]
    if empty:
        print(
            "error: validation gate matched no tests: " + ", ".join(empty),
            file=sys.stderr,
        )
        return 2

    if args.list:
        for gate, files in selections:
            print(f"{gate.name} ({', '.join(gate.patterns)}):")
            for path in files:
                print(f"  {path.relative_to(ROOT)}")
        return 0

    failures: list[str] = []
    for gate, files in selections:
        print(f"\n=== StageGuard gate: {gate.name} ({len(files)} files) ===", flush=True)
        gate_failed = False
        for path in files:
            print(f"--- {path.name} ---", flush=True)
            completed = subprocess.run(_command(path), cwd=ROOT, check=False)
            if completed.returncode != 0:
                gate_failed = True
                failures.append(f"{gate.name}/{path.name}")
                if not args.keep_going:
                    break
        if gate_failed and not args.keep_going:
            break

    if failures:
        print("\nFAILED tests: " + ", ".join(failures), file=sys.stderr)
        return 1

    print("\nAll selected StageGuard validation gates passed.")
    print("Live Docker/Grafana MCP smoke is intentionally not part of this runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
