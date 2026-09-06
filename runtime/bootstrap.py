#!/usr/bin/env python3
"""Production-oriented StageGuard runtime bootstrap.

This module is intentionally boring: it turns validated files + process-owned
secrets into the already-bounded StageGuard runtime. It does not accept PromQL,
datasource IDs, actions, or remediation targets over HTTP.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from activation import ActivationRecord, load_activation_record
from api import make_server
from identity import IdentityProvider, LocalDevelopmentIdentityProvider, StaticBearerIdentityProvider
from incident_service import IncidentService, JsonlAuditLog
from mcp_metric_client import McpPrometheusMetricClient
from onboarding import load_telemetry_profile
from remediation import ActionResult, RemediationClient, SimulatorRemediationClient
from telemetry import DEFAULT_TELEMETRY_PROFILE, TelemetryProfile


class DisabledRemediationClient:
    """Safe production default until an explicit write adapter is configured."""

    def recover_uplink(self, production_id: str, uplink: str) -> ActionResult:
        return ActionResult(False, "no production remediation adapter is configured")


@dataclass
class RuntimeBundle:
    service: IncidentService
    metrics: McpPrometheusMetricClient
    identity_provider: IdentityProvider
    host: str
    port: int

    def close(self) -> None:
        self.metrics.close()


def _read_required_secret(env_name: str) -> str:
    value = os.getenv(env_name, "")
    if not value:
        raise ValueError(f"required environment variable {env_name} is not set")
    return value


def _identity_provider(host: str, *, token_env: str, subject_env: str) -> IdentityProvider:
    """Use implicit local identity only on loopback; otherwise require bearer auth."""
    from api import _is_loopback

    if _is_loopback(host):
        # Operators may still opt into bearer auth locally by setting the token.
        token = os.getenv(token_env, "")
        if not token:
            return LocalDevelopmentIdentityProvider()
    else:
        token = _read_required_secret(token_env)

    subject = os.getenv(subject_env, "stageguard-operator").strip()
    if not subject:
        raise ValueError(f"{subject_env} must not be blank")
    return StaticBearerIdentityProvider({token: subject})


def build_runtime(
    *,
    telemetry_config: str | Path,
    activation_path: str | Path | None,
    audit_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 9110,
    token_env: str = "STAGEGUARD_API_TOKEN",
    subject_env: str = "STAGEGUARD_API_SUBJECT",
    metrics_factory: Callable[[], McpPrometheusMetricClient] = McpPrometheusMetricClient,
    remediation_factory: Callable[[TelemetryProfile], RemediationClient] | None = None,
    activation_now_unix: int | None = None,
) -> RuntimeBundle:
    """Construct the complete runtime and enforce startup trust boundaries.

    Production mappings always require a matching activation artifact. The
    datasource identity is taken from the actual MCP metric client instance and
    therefore cannot drift from the identity verified by ``IncidentService``.
    """
    profile = load_telemetry_profile(telemetry_config)
    metrics = metrics_factory()
    activation: ActivationRecord | None = None
    try:
        if activation_path is not None:
            activation = load_activation_record(activation_path)
        elif profile != DEFAULT_TELEMETRY_PROFILE:
            raise ValueError("non-default production telemetry requires --activation")

        identity = _identity_provider(host, token_env=token_env, subject_env=subject_env)
        audit = JsonlAuditLog(audit_path)

        if remediation_factory is not None:
            remediation = remediation_factory(profile)
        elif profile == DEFAULT_TELEMETRY_PROFILE:
            remediation = SimulatorRemediationClient()
        else:
            # Deliberately safe: production diagnosis/API can run, but execute
            # cannot mutate infrastructure until an explicit adapter is wired.
            remediation = DisabledRemediationClient()

        service = IncidentService(
            metrics,
            remediation,
            audit,
            telemetry_profile=profile,
            activation_record=activation,
            datasource_identity=metrics.datasource_uid if activation is not None else None,
            activation_now_unix=activation_now_unix,
        )

        # Constructing the server validates the final network/auth boundary now,
        # before the caller begins serving requests.
        server = make_server(service, host, port, identity_provider=identity)
        server.server_close()
        return RuntimeBundle(service, metrics, identity, host, port)
    except Exception:
        metrics.close()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the StageGuard incident API")
    parser.add_argument("--telemetry-config", required=True, help="strict versioned telemetry mapping JSON")
    parser.add_argument("--activation", help="fresh activation artifact produced by preflight")
    parser.add_argument("--audit-log", default=".stageguard/audit.jsonl", help="append-only local audit path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9110)
    parser.add_argument("--token-env", default="STAGEGUARD_API_TOKEN", help="name of env var containing bearer token")
    parser.add_argument("--subject-env", default="STAGEGUARD_API_SUBJECT", help="name of env var containing operator subject")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        bundle = build_runtime(
            telemetry_config=args.telemetry_config,
            activation_path=args.activation,
            audit_path=args.audit_log,
            host=args.host,
            port=args.port,
            token_env=args.token_env,
            subject_env=args.subject_env,
        )
    except Exception as exc:
        print(f"StageGuard startup refused: {exc}", file=sys.stderr)
        return 2

    server = make_server(
        bundle.service,
        bundle.host,
        bundle.port,
        identity_provider=bundle.identity_provider,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        bundle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
