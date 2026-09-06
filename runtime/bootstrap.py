#!/usr/bin/env python3
"""Production-oriented StageGuard runtime bootstrap.

This module turns validated files + process-owned secrets into the bounded
StageGuard runtime. It does not accept PromQL, datasource IDs, actions, or
remediation targets over HTTP.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from activation import ActivationRecord, load_activation_record
from api import _is_loopback, make_server
from http_remediation_transport import HttpRemediationTransport
from identity import IdentityProvider, LocalDevelopmentIdentityProvider, StaticBearerIdentityProvider
from incident_service import IncidentService, JsonlAuditLog
from mcp_metric_client import McpPrometheusMetricClient
from onboarding import load_telemetry_profile
from production_remediation import AllowlistedProductionRemediationClient
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
    server: ThreadingHTTPServer

    def close(self) -> None:
        self.server.server_close()
        self.metrics.close()


def _read_required_secret(env_name: str) -> str:
    value = os.getenv(env_name, "")
    if not value:
        raise ValueError(f"required environment variable {env_name} is not set")
    return value


def _identity_provider(host: str, *, token_env: str, subject_env: str) -> IdentityProvider:
    """Use implicit local identity only on loopback; otherwise require bearer auth."""
    if _is_loopback(host):
        token = os.getenv(token_env, "")
        if not token:
            return LocalDevelopmentIdentityProvider()
    else:
        token = _read_required_secret(token_env)

    subject = os.getenv(subject_env, "stageguard-operator").strip()
    if not subject:
        raise ValueError(f"{subject_env} must not be blank")
    return StaticBearerIdentityProvider({token: subject})


def _production_remediation_from_env(
    profile: TelemetryProfile,
    *,
    endpoint_env: str,
    token_env: str,
) -> AllowlistedProductionRemediationClient:
    endpoint = _read_required_secret(endpoint_env)
    token = _read_required_secret(token_env)
    transport = HttpRemediationTransport(endpoint, token)
    return AllowlistedProductionRemediationClient(
        transport,
        allowed_production_id=profile.production_id,
        allowed_uplink=profile.affected_uplink,
    )


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
    enable_production_remediation: bool = False,
    remediation_endpoint_env: str = "STAGEGUARD_REMEDIATION_ENDPOINT",
    remediation_token_env: str = "STAGEGUARD_REMEDIATION_TOKEN",
    activation_now_unix: int | None = None,
) -> RuntimeBundle:
    """Construct the complete runtime and enforce startup trust boundaries.

    Production mappings always require a matching activation artifact. The
    datasource identity is taken from the actual MCP metric client instance and
    therefore cannot drift from the identity verified by ``IncidentService``.
    Production writes remain disabled unless the host injects a factory or the
    CLI explicitly opts into the credential-isolated HTTPS transport.
    """
    profile = load_telemetry_profile(telemetry_config)
    metrics = metrics_factory()
    activation: ActivationRecord | None = None
    server: ThreadingHTTPServer | None = None
    try:
        if activation_path is not None:
            activation = load_activation_record(activation_path)
        elif profile != DEFAULT_TELEMETRY_PROFILE:
            raise ValueError("non-default production telemetry requires --activation")

        if remediation_factory is not None and enable_production_remediation:
            raise ValueError("choose either remediation_factory or explicit production remediation, not both")
        if enable_production_remediation and profile == DEFAULT_TELEMETRY_PROFILE:
            raise ValueError("explicit production remediation is not permitted for the demo telemetry profile")

        identity = _identity_provider(host, token_env=token_env, subject_env=subject_env)
        audit = JsonlAuditLog(audit_path)

        if remediation_factory is not None:
            remediation = remediation_factory(profile)
        elif enable_production_remediation:
            remediation = _production_remediation_from_env(
                profile,
                endpoint_env=remediation_endpoint_env,
                token_env=remediation_token_env,
            )
        elif profile == DEFAULT_TELEMETRY_PROFILE:
            remediation = SimulatorRemediationClient()
        else:
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
        server = make_server(service, host, port, identity_provider=identity)
        return RuntimeBundle(service, metrics, identity, server)
    except Exception:
        if server is not None:
            server.server_close()
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
    parser.add_argument(
        "--enable-production-remediation",
        action="store_true",
        help="explicitly enable the allowlisted HTTPS production write adapter",
    )
    parser.add_argument(
        "--remediation-endpoint-env",
        default="STAGEGUARD_REMEDIATION_ENDPOINT",
        help="name of env var containing the fixed HTTPS remediation endpoint",
    )
    parser.add_argument(
        "--remediation-token-env",
        default="STAGEGUARD_REMEDIATION_TOKEN",
        help="name of env var containing the separate remediation bearer credential",
    )
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
            enable_production_remediation=args.enable_production_remediation,
            remediation_endpoint_env=args.remediation_endpoint_env,
            remediation_token_env=args.remediation_token_env,
        )
    except Exception as exc:
        print(f"StageGuard startup refused: {exc}", file=sys.stderr)
        return 2

    try:
        bundle.server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        bundle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
