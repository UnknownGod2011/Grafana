#!/usr/bin/env python3
"""CLI for proving a StageGuard telemetry profile before activation."""
from __future__ import annotations

import argparse
import json
import sys

from mcp_metric_client import McpPrometheusMetricClient
from onboarding import load_telemetry_profile, preflight_telemetry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and preflight a StageGuard telemetry profile")
    parser.add_argument("config", help="Path to versioned telemetry JSON")
    args = parser.parse_args()

    try:
        profile = load_telemetry_profile(args.config)
        with McpPrometheusMetricClient() as client:
            result = preflight_telemetry(client, profile)
    except Exception as exc:
        print(json.dumps({"ready": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.ready else 3


if __name__ == "__main__":
    sys.exit(main())
