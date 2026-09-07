#!/usr/bin/env python3
"""CLI for proving and pinning StageGuard metric + Loki evidence before activation."""
from __future__ import annotations

import argparse
import json
import sys

from activation import create_activation_record, write_activation_record
from log_activation import create_log_activation_record, preflight_loki, write_log_activation_record
from mcp_log_client import McpLokiLogClient
from mcp_metric_client import McpPrometheusMetricClient
from onboarding import load_telemetry_profile, preflight_telemetry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and preflight StageGuard telemetry + log evidence")
    parser.add_argument("config", help="Path to versioned telemetry JSON")
    parser.add_argument(
        "--activation-output",
        help="Write a pinned metric activation record only when all eight metric checks succeed",
    )
    parser.add_argument(
        "--log-activation-output",
        help="Write a pinned Loki activation record only when the bounded causal query preflight succeeds",
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
        with McpPrometheusMetricClient() as metric_client:
            metric_result = preflight_telemetry(metric_client, profile)
            metric_activation = None
            if metric_result.ready and args.activation_output:
                metric_activation = create_activation_record(
                    profile,
                    metric_client.datasource_uid,
                    metric_result,
                    ttl_seconds=args.ttl_seconds,
                )
                write_activation_record(args.activation_output, metric_activation)

        with McpLokiLogClient() as log_client:
            log_result = preflight_loki(log_client, profile)
            log_activation = None
            if log_result.ready and args.log_activation_output:
                log_activation = create_log_activation_record(
                    profile,
                    log_client.datasource_uid,
                    log_result,
                    ttl_seconds=args.ttl_seconds,
                )
                write_log_activation_record(args.log_activation_output, log_activation)
    except Exception as exc:
        print(json.dumps({"ready": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2

    ready = metric_result.ready and log_result.ready
    payload = {
        "production_id": profile.production_id,
        "ready": ready,
        "metrics": metric_result.to_dict(),
        "loki": log_result.to_dict(),
    }
    if metric_activation is not None:
        payload["activation"] = metric_activation.to_dict()
        payload["activation_path"] = args.activation_output
    if log_activation is not None:
        payload["log_activation"] = log_activation.to_dict()
        payload["log_activation_path"] = args.log_activation_output
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ready else 3


if __name__ == "__main__":
    sys.exit(main())
