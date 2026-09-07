#!/usr/bin/env python3
"""Fail-closed StageGuard evidence-plane readiness checks.

Readiness is intentionally distinct from process liveness. The probe verifies
activation freshness and pinned datasource identities, then performs the
read-only MCP initialize/tools-list handshake plus one bounded datasource lookup
per evidence plane. It never executes PromQL or LogQL and never returns raw
configuration, datasource identifiers, queries, credentials, or provider errors.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from activation import ActivationRecord, verify_activation_record
from log_activation import LogActivationRecord, verify_log_activation_record
from mcp_log_client import McpLokiLogClient
from mcp_metric_client import McpPrometheusMetricClient
from telemetry import TelemetryProfile


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    checks: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {"ready": self.ready, "checks": dict(self.checks)}


def _verify_mcp_datasource_access(client: object, datasource_uid: str) -> None:
    """Prove the configured UID is readable through Grafana without a data query.

    ``connect()`` verifies the expected query tool exists and is read-only, but
    tools/list alone need not contact Grafana. ``get_datasource`` is a bounded,
    idempotent, read-only Grafana API call and therefore also proves credential,
    organization, network, and datasource-scope access without consuming live
    metric/log evidence.
    """
    connect = getattr(client, "connect")
    connect()
    transport = getattr(client, "_client", None)
    if transport is None:
        raise RuntimeError("MCP transport unavailable after connect")
    result = transport.request(
        "tools/call",
        {"name": "get_datasource", "arguments": {"uid": datasource_uid}},
    )
    if not isinstance(result, dict) or result.get("isError"):
        raise RuntimeError("datasource lookup failed")


class EvidencePlaneReadinessProbe:
    """Verify that StageGuard can safely receive incident traffic.

    A failed check is represented only by its bounded public status. Exception
    messages are deliberately discarded because SDK/MCP errors can contain
    endpoints, credentials, datasource names, or query fragments.
    """

    def __init__(
        self,
        profile: TelemetryProfile,
        activation: ActivationRecord | None,
        log_activation: LogActivationRecord | None,
        metrics: McpPrometheusMetricClient,
        logs: McpLokiLogClient | None,
        *,
        now_unix: Callable[[], int] | None = None,
    ) -> None:
        self._profile = profile
        self._activation = activation
        self._log_activation = log_activation
        self._metrics = metrics
        self._logs = logs
        self._now_unix = now_unix
        self._lock = threading.Lock()

    def _now(self) -> int | None:
        return None if self._now_unix is None else int(self._now_unix())

    def check(self) -> ReadinessResult:
        checks: dict[str, str] = {}
        with self._lock:
            if self._activation is None:
                checks["metric_activation"] = "missing"
            else:
                try:
                    verify_activation_record(
                        self._activation,
                        self._profile,
                        self._metrics.datasource_uid,
                        now_unix=self._now(),
                    )
                    checks["metric_activation"] = "ok"
                except Exception:
                    checks["metric_activation"] = "failed"

            if self._log_activation is None or self._logs is None:
                checks["loki_activation"] = "missing"
            else:
                try:
                    verify_log_activation_record(
                        self._log_activation,
                        self._profile,
                        self._logs.datasource_uid,
                        now_unix=self._now(),
                    )
                    checks["loki_activation"] = "ok"
                except Exception:
                    checks["loki_activation"] = "failed"

            try:
                _verify_mcp_datasource_access(self._metrics, self._metrics.datasource_uid)
                checks["prometheus_mcp"] = "ok"
            except Exception:
                checks["prometheus_mcp"] = "failed"

            if self._logs is None:
                checks["loki_mcp"] = "missing"
            else:
                try:
                    _verify_mcp_datasource_access(self._logs, self._logs.datasource_uid)
                    checks["loki_mcp"] = "ok"
                except Exception:
                    checks["loki_mcp"] = "failed"

        return ReadinessResult(
            ready=bool(checks) and all(status == "ok" for status in checks.values()),
            checks=checks,
        )
