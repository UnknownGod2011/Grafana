#!/usr/bin/env python3
"""Run StageGuard's dependency-light safety and Grafana/MCP regression gates.

This runner intentionally executes unittest groups in separate processes so a
failure is attributed to a boundary instead of being buried in one large test
run. It does not start Docker, contact Grafana, trigger GitHub Actions, or read
credentials; live MCP smoke remains an explicit follow-up gate.
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
    pattern: str


GATES = (
    Gate("timeline disclosure", "test_timeline*.py"),
    Gate("public audit", "test_*audit*.py"),
    Gate("execution safety", "test_*execution*.py"),
    Gate("Grafana MCP", "test_*mcp*.py"),
)


def _command(pattern: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(TESTS),
        "-p",
        pattern,
        "-t",
        str(ROOT),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dependency-light StageGuard safety/MCP regression gates."
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="run every gate even after a failure (default: fail fast)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the gates without executing tests",
    )
    args = parser.parse_args()

    if not TESTS.is_dir():
        print(f"error: test directory not found: {TESTS}", file=sys.stderr)
        return 2

    if args.list:
        for gate in GATES:
            print(f"{gate.name}: {gate.pattern}")
        return 0

    failures: list[str] = []
    for gate in GATES:
        print(f"\n=== StageGuard gate: {gate.name} ({gate.pattern}) ===", flush=True)
        completed = subprocess.run(_command(gate.pattern), cwd=ROOT, check=False)
        if completed.returncode != 0:
            failures.append(gate.name)
            if not args.keep_going:
                break

    if failures:
        print("\nFAILED gates: " + ", ".join(failures), file=sys.stderr)
        return 1

    print("\nAll selected StageGuard validation gates passed.")
    print("Live Docker/Grafana MCP smoke is intentionally not part of this runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
