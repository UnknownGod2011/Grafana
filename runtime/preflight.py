#!/usr/bin/env python3
"""CLI for proving and pinning a StageGuard telemetry profile before activation."""
from __future__ import annotations

import argparse
import json
import sys

from activation import create_activation_record, write_activation_record
from mcp_metric_client import McpPrometheusMetricClient
from onboarding import load_telemetry_profile, preflight_telemetry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and preflight a StageGuard telemetry profile")
    parser.add_argument("config", help="Path to versioned telemetry JSON")
    parser.add_argument(
        "--activation-output",
        help="Write a pinned activation record only when all eight checks succeed",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=24 * 60 * 60,
        help="Activation validity window in seconds (default: 86400, max: 604800)",
    )
    args = parser.parse_args()

    try:
        profile = load_telemetry_profile(args.config)
        with McpPrometheusMetricClient() as client:
            result = preflight_telemetry(client, profile)
            activation = None
            if result.ready and args.activation_output:
                activation = create_activation_record(
                    profile,
                    client.datasource_uid,
                    result,
                    ttl_seconds=args.ttl_seconds,
                )
                write_activation_record(args.activation_output, activation)
    except Exception as exc:
        print(json.dumps({"ready": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2

    payload = result.to_dict()
    if activation is not None:
        payload["activation"] = activation.to_dict()
        payload["activation_path"] = args.activation_output
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.ready else 3


if __name__ == "__main__":
    sys.exit(main())
