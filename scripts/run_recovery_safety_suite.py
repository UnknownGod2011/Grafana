#!/usr/bin/env python3
"""Run StageGuard's fast recovery/no-replay safety regression suite.

This runner intentionally exercises the recovery state contract across service,
API, restart durability, observability, and the real embedded operator-console
JavaScript. It is dependency-light and does not require Grafana, Gemini,
provider credentials, Docker, or paid cloud resources.

Node.js is required because the operator-console DOM harnesses execute the real
browser JavaScript through Node's built-in ``vm`` module. Missing Node is treated
as a failure here rather than silently accepting skipped browser safety tests.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


TEST_MODULES = (
    "tests.test_recovery_observability",
    "tests.test_anchored_recovery_recheck",
    "tests.test_api_recovery_recheck",
    "tests.test_recovery_recheck_restart",
    "tests.test_operator_console_dom",
    "tests.test_operator_console_dom_requests",
)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = repo_root / "runtime"

    if not runtime_dir.is_dir():
        print(f"error: runtime directory not found: {runtime_dir}", file=sys.stderr)
        return 2

    node = shutil.which("node")
    if node is None:
        print(
            "error: Node.js is required for recovery safety validation; "
            "operator-console DOM tests must not be silently skipped.",
            file=sys.stderr,
        )
        return 2

    print(f"StageGuard recovery safety suite (Node: {node})")
    command = [sys.executable, "-m", "unittest", "-v", *TEST_MODULES]
    completed = subprocess.run(command, cwd=runtime_dir, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
