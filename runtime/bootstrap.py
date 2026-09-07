#!/usr/bin/env python3
"""Production-oriented StageGuard runtime bootstrap.

This module turns validated files + process-owned secrets into the bounded
StageGuard runtime. It does not accept PromQL, LogQL, datasource IDs, actions,
or remediation targets over HTTP.
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
from cloud_audit import GoogleCloudLoggingAuditSink
from durable_audit_reader import GoogleCloudAuditReader
from gemini_commander import GeminiCommander, GoogleGenAICommanderModel
from http_remediation_transport import HttpRemediationTransport
from identity import (
    GoogleIapIdentityProvider,
    IdentityProvider,
    LocalDevelopmentIdentityProvider,
    StaticBearerIdentityProvider,
)
from incident_checkpoint import CheckpointStore, GoogleCloudStorageCheckpointStore, JsonCheckpointStore
from incident_service import AuditReader, AuditSink, IncidentService, JsonlAuditLog
from log_activation import LogActivationRecord, load_log_activation_record, verify_log_activation_record
from mcp_log_client import McpLokiLogClient
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
    logs: McpLokiLogClient | None
    identity_provider: IdentityProvider
    server: ThreadingHTTPServer

    def close(self) -> None:
        self.server.server_close()
        if self.logs is not None:
            self.logs.close()
        self.metrics.close()


def _read_required_secret(env_name: str) -> str:
    value = os.getenv(env_name, "")
    if not value:
        raise ValueError(f"required environment variable {env_name} is not set")
    return value


def _identity_provider(
    host: str,
    *,
    mode: str,
    token_env: str,
    subject_env: str,
    iap_audience_env: str,
) -> IdentityProvider:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"auto", "local", "bearer", "iap"}:
        raise ValueError("identity mode must be one of auto, local, bearer, iap")
    iap_audience = os.getenv(iap_audience_env, "").strip()
    token = os.getenv(token_env, "")
    if normalized_mode == "iap" or (normalized_mode == "auto" and iap_audience):
        if not iap_audience:
            raise ValueError(f"required environment variable {iap_audience_env} is not set")
        return GoogleIapIdentityProvider(iap_audience)
    if normalized_mode == "local":
        if not _is_loopback(host):
            raise ValueError("local identity is permitted only on loopback")
        return LocalDevelopmentIdentityProvider()
    if normalized_mode == "auto" and _is_loopback(host) and not token:
        return LocalDevelopmentIdentityProvider()
    if normalized_mode in {"auto", "bearer"}:
        token = token or _read_required_secret(token_env)
        subject = os.getenv(subject_env, "stageguard-operator").strip()
        if not subject:
            raise ValueError(f"{subject_env} must not be blank")
        return StaticBearerIdentityProvider({token: subject})
    raise ValueError("unable to configure identity provider")


def _audit_sink(*, backend: str, audit_path: str | Path, cloud_project_env: str, cloud_log_name: str) -> AuditSink:
    normalized = backend.strip().lower()
    if normalized == "jsonl":
        return JsonlAuditLog(audit_path)
    if normalized == "cloud-logging":
        project = os.getenv(cloud_project_env, "").strip() or None
        return GoogleCloudLoggingAuditSink.from_environment(project=project, log_name=cloud_log_name)
    raise ValueError("audit backend must be jsonl or cloud-logging")


def _audit_reader(*, backend: str, cloud_project_env: str, cloud_log_name: str) -> AuditReader | None:
    normalized = backend.strip().lower()
    if normalized == "jsonl":
        return None
    if normalized == "cloud-logging":
        project = os.getenv(cloud_project_env, "").strip() or None
        return GoogleCloudAuditReader.from_environment(project=project, log_name=cloud_log_name)
    raise ValueError("audit backend must be jsonl or cloud-logging")


def _checkpoint_store(
    *,
    backend: str,
    checkpoint_path: str | Path,
    checkpoint_bucket_env: str,
    checkpoint_object: str,
    cloud_project_env: str,
) -> CheckpointStore | None:
    normalized = backend.strip().lower()
    if normalized == "none":
        return None
    if normalized == "json":
        return JsonCheckpointStore(checkpoint_path)
    if normalized == "gcs":
        bucket = _read_required_secret(checkpoint_bucket_env)
        project = os.getenv(cloud_project_env, "").strip() or None
        return GoogleCloudStorageCheckpointStore.from_environment(
            bucket_name=bucket,
            project=project,
            object_name=checkpoint_object,
        )
    raise ValueError("checkpoint backend must be none, json, or gcs")


def _production_remediation_from_env(profile: TelemetryProfile, *, endpoint_env: str, token_env: str) -> AllowlistedProductionRemediationClient:
    transport = HttpRemediationTransport(_read_required_secret(endpoint_env), _read_required_secret(token_env))
    return AllowlistedProductionRemediationClient(
        transport,
        allowed_production_id=profile.production_id,
        allowed_uplink=profile.affected_uplink,
    )


def _gemini_commander_from_environment() -> GeminiCommander:
    return GeminiCommander(GoogleGenAICommanderModel.from_vertex_ai_environment())


def build_runtime(
    *,
    telemetry_config: str | Path,
    activation_path: str | Path | None,
    log_activation_path: str | Path | None = None,
    audit_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 9110,
    identity_mode: str = "auto",
    token_env: str = "STAGEGUARD_API_TOKEN",
    subject_env: str = "STAGEGUARD_API_SUBJECT",
    iap_audience_env: str = "STAGEGUARD_IAP_AUDIENCE",
    audit_backend: str = "jsonl",
    cloud_project_env: str = "GOOGLE_CLOUD_PROJECT",
    cloud_log_name: str = "stageguard-audit",
    checkpoint_backend: str = "none",
    checkpoint_path: str | Path = ".stageguard/incident-checkpoint.json",
    checkpoint_bucket_env: str = "STAGEGUARD_CHECKPOINT_BUCKET",
    checkpoint_object: str = "stageguard/incident-checkpoint.json",
    metrics_factory: Callable[[], McpPrometheusMetricClient] = McpPrometheusMetricClient,
    logs_factory: Callable[[], McpLokiLogClient] = McpLokiLogClient,
    remediation_factory: Callable[[TelemetryProfile], RemediationClient] | None = None,
    enable_production_remediation: bool = False,
    remediation_endpoint_env: str = "STAGEGUARD_REMEDIATION_ENDPOINT",
    remediation_token_env: str = "STAGEGUARD_REMEDIATION_TOKEN",
    enable_gemini: bool = False,
    commander_factory: Callable[[], GeminiCommander] = _gemini_commander_from_environment,
    activation_now_unix: int | None = None,
) -> RuntimeBundle:
    """Construct runtime with pinned evidence, trusted identity, bounded audit and optional restart state."""
    profile = load_telemetry_profile(telemetry_config)
    metrics = metrics_factory()
    logs: McpLokiLogClient | None = None
    activation: ActivationRecord | None = None
    log_activation: LogActivationRecord | None = None
    server: ThreadingHTTPServer | None = None
    try:
        if activation_path is not None:
            activation = load_activation_record(activation_path)
        elif profile != DEFAULT_TELEMETRY_PROFILE:
            raise ValueError("non-default production telemetry requires --activation")

        if profile != DEFAULT_TELEMETRY_PROFILE:
            if log_activation_path is None:
                raise ValueError("non-default production telemetry requires --log-activation")
            log_activation = load_log_activation_record(log_activation_path)
            logs = logs_factory()
            verify_log_activation_record(log_activation, profile, logs.datasource_uid, now_unix=activation_now_unix)
        elif log_activation_path is not None:
            log_activation = load_log_activation_record(log_activation_path)
            logs = logs_factory()
            verify_log_activation_record(log_activation, profile, logs.datasource_uid, now_unix=activation_now_unix)

        if remediation_factory is not None and enable_production_remediation:
            raise ValueError("choose either remediation_factory or explicit production remediation, not both")
        if enable_production_remediation and profile == DEFAULT_TELEMETRY_PROFILE:
            raise ValueError("explicit production remediation is not permitted for the demo telemetry profile")

        identity = _identity_provider(host, mode=identity_mode, token_env=token_env, subject_env=subject_env, iap_audience_env=iap_audience_env)
        audit = _audit_sink(backend=audit_backend, audit_path=audit_path, cloud_project_env=cloud_project_env, cloud_log_name=cloud_log_name)
        audit_reader = _audit_reader(backend=audit_backend, cloud_project_env=cloud_project_env, cloud_log_name=cloud_log_name)
        checkpoint_store = _checkpoint_store(
            backend=checkpoint_backend,
            checkpoint_path=checkpoint_path,
            checkpoint_bucket_env=checkpoint_bucket_env,
            checkpoint_object=checkpoint_object,
            cloud_project_env=cloud_project_env,
        )

        if remediation_factory is not None:
            remediation = remediation_factory(profile)
        elif enable_production_remediation:
            remediation = _production_remediation_from_env(profile, endpoint_env=remediation_endpoint_env, token_env=remediation_token_env)
        elif profile == DEFAULT_TELEMETRY_PROFILE:
            remediation = SimulatorRemediationClient()
        else:
            remediation = DisabledRemediationClient()

        commander = commander_factory() if enable_gemini else None
        service = IncidentService(
            metrics,
            remediation,
            audit,
            audit_reader=audit_reader,
            checkpoint_store=checkpoint_store,
            telemetry_profile=profile,
            activation_record=activation,
            datasource_identity=metrics.datasource_uid if activation is not None else None,
            logs=logs,
            log_activation_record=log_activation,
            commander=commander,
            activation_now_unix=activation_now_unix,
        )
        server = make_server(service, host, port, identity_provider=identity)
        return RuntimeBundle(service, metrics, logs, identity, server)
    except Exception:
        if server is not None:
            server.server_close()
        if logs is not None:
            logs.close()
        metrics.close()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the StageGuard incident API")
    parser.add_argument("--telemetry-config", required=True, help="strict versioned telemetry mapping JSON")
    parser.add_argument("--activation", help="fresh metric activation artifact produced by preflight")
    parser.add_argument("--log-activation", help="fresh Loki evidence activation artifact produced by preflight")
    parser.add_argument("--audit-log", default=".stageguard/audit.jsonl", help="append-only local audit path")
    parser.add_argument("--audit-backend", choices=("jsonl", "cloud-logging"), default="jsonl")
    parser.add_argument("--cloud-project-env", default="GOOGLE_CLOUD_PROJECT")
    parser.add_argument("--cloud-log-name", default="stageguard-audit")
    parser.add_argument("--checkpoint-backend", choices=("none", "json", "gcs"), default="json")
    parser.add_argument("--checkpoint-path", default=".stageguard/incident-checkpoint.json")
    parser.add_argument("--checkpoint-bucket-env", default="STAGEGUARD_CHECKPOINT_BUCKET")
    parser.add_argument("--checkpoint-object", default="stageguard/incident-checkpoint.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9110)
    parser.add_argument("--identity-mode", choices=("auto", "local", "bearer", "iap"), default="auto")
    parser.add_argument("--token-env", default="STAGEGUARD_API_TOKEN", help="name of env var containing bearer token")
    parser.add_argument("--subject-env", default="STAGEGUARD_API_SUBJECT", help="name of env var containing operator subject")
    parser.add_argument("--iap-audience-env", default="STAGEGUARD_IAP_AUDIENCE", help="name of env var containing the exact IAP Signed Header JWT audience")
    parser.add_argument("--enable-gemini", action="store_true", help="enable revision-bound advisory Gemini briefings using Vertex AI environment/ADC")
    parser.add_argument("--enable-production-remediation", action="store_true", help="explicitly enable the allowlisted HTTPS production write adapter")
    parser.add_argument("--remediation-endpoint-env", default="STAGEGUARD_REMEDIATION_ENDPOINT", help="name of env var containing the fixed HTTPS remediation endpoint")
    parser.add_argument("--remediation-token-env", default="STAGEGUARD_REMEDIATION_TOKEN", help="name of env var containing the separate remediation bearer credential")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        bundle = build_runtime(
            telemetry_config=args.telemetry_config,
            activation_path=args.activation,
            log_activation_path=args.log_activation,
            audit_path=args.audit_log,
            audit_backend=args.audit_backend,
            cloud_project_env=args.cloud_project_env,
            cloud_log_name=args.cloud_log_name,
            checkpoint_backend=args.checkpoint_backend,
            checkpoint_path=args.checkpoint_path,
            checkpoint_bucket_env=args.checkpoint_bucket_env,
            checkpoint_object=args.checkpoint_object,
            host=args.host,
            port=args.port,
            identity_mode=args.identity_mode,
            token_env=args.token_env,
            subject_env=args.subject_env,
            iap_audience_env=args.iap_audience_env,
            enable_gemini=args.enable_gemini,
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
