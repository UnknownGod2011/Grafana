#!/usr/bin/env python3
"""Fail-closed StageGuard evidence-plane readiness checks.

Readiness is intentionally distinct from process liveness. Activation expiry and
semantic/datasource pins are verified locally on every request. External Grafana
MCP datasource probes are cached for a short bounded TTL so health polling cannot
stampede Grafana. A previously successful probe may be reported as ``stale`` for
only a bounded grace window after a transient refresh failure; activation failure
is never masked by that grace.

Local trust checks are deliberately evaluated before any network work. If either
activation record is missing or invalid, the corresponding readiness evaluation
cannot succeed, so StageGuard reports external MCP checks as ``blocked`` without
spawning/connecting an MCP client. This prevents a misconfigured or expired local
trust state from creating avoidable load against Grafana.

The module also exposes a small Prometheus text surface containing only fixed
StageGuard readiness metrics. It never emits datasource identifiers, endpoints,
queries, credentials, activation hashes, exception messages, or raw evidence.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

from activation import ActivationRecord, verify_activation_record
from log_activation import LogActivationRecord, verify_log_activation_record
from mcp_log_client import McpLokiLogClient
from mcp_metric_client import McpPrometheusMetricClient
from telemetry import TelemetryProfile


MAX_EXTERNAL_PROBE_TTL_SECONDS = 300.0
MAX_FAILURE_BACKOFF_SECONDS = 300.0
MAX_STALE_GRACE_SECONDS = 900.0


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    checks: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {"ready": self.ready, "checks": dict(self.checks)}


class _McpReadinessError(RuntimeError):
    """Internal error carrying only a bounded failure class, never provider text."""

    def __init__(self, failure_class: str) -> None:
        super().__init__(failure_class)
        self.failure_class = failure_class


@dataclass
class _ExternalProbeState:
    last_success_monotonic: float | None = None
    next_probe_monotonic: float = 0.0
    public_status: str = "failed"


def _bounded_seconds(name: str, value: object, maximum: float) -> float:
    """Return a finite positive timing value inside a fixed safety envelope."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number of seconds")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0 or normalized > maximum:
        raise ValueError(f"{name} must be greater than 0 and at most {maximum:g} seconds")
    return normalized


def _verify_mcp_datasource_access(client: object, datasource_uid: str) -> None:
    """Prove the configured UID is readable through Grafana without a data query."""
    connect = getattr(client, "connect")
    try:
        connect()
    except Exception as exc:
        raise _McpReadinessError("connect") from exc

    transport = getattr(client, "_client", None)
    if transport is None:
        raise _McpReadinessError("connect")
    try:
        result = transport.request(
            "tools/call",
            {"name": "get_datasource", "arguments": {"uid": datasource_uid}},
        )
    except Exception as exc:
        raise _McpReadinessError("lookup") from exc
    if not isinstance(result, dict) or result.get("isError"):
        raise _McpReadinessError("lookup")


class EvidencePlaneReadinessProbe:
    """Verify that StageGuard can safely receive incident traffic.

    Local activation verification always runs. External MCP probes run only when
    all required local activation checks pass, then use a bounded cache and
    single-flight lock. ``stale`` is readiness-eligible only while a prior
    successful external probe remains inside ``stale_grace_seconds``.
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
        monotonic: Callable[[], float] | None = None,
        external_probe_ttl_seconds: float = 15.0,
        failure_backoff_seconds: float = 5.0,
        stale_grace_seconds: float = 30.0,
    ) -> None:
        ttl = _bounded_seconds(
            "external_probe_ttl_seconds",
            external_probe_ttl_seconds,
            MAX_EXTERNAL_PROBE_TTL_SECONDS,
        )
        backoff = _bounded_seconds(
            "failure_backoff_seconds",
            failure_backoff_seconds,
            MAX_FAILURE_BACKOFF_SECONDS,
        )
        stale_grace = _bounded_seconds(
            "stale_grace_seconds",
            stale_grace_seconds,
            MAX_STALE_GRACE_SECONDS,
        )
        if stale_grace < ttl:
            raise ValueError("stale_grace_seconds must be at least the probe TTL")
        self._profile = profile
        self._activation = activation
        self._log_activation = log_activation
        self._metrics = metrics
        self._logs = logs
        self._now_unix = now_unix
        self._monotonic = monotonic or time.monotonic
        self._ttl = ttl
        self._failure_backoff = backoff
        self._stale_grace = stale_grace
        self._lock = threading.Lock()
        self._external = {
            "prometheus": _ExternalProbeState(),
            "loki": _ExternalProbeState(),
        }
        self._check_total = 0
        self._external_attempts = {"prometheus": 0, "loki": 0}
        self._external_failures = {
            "prometheus": {"connect": 0, "lookup": 0, "unknown": 0},
            "loki": {"connect": 0, "lookup": 0, "unknown": 0},
        }
        self._last_latency_seconds = {"prometheus": 0.0, "loki": 0.0}
        self._last_ready = False

    def _now(self) -> int | None:
        return None if self._now_unix is None else int(self._now_unix())

    def _external_status(self, plane: str, client: object, datasource_uid: str, now: float) -> str:
        state = self._external[plane]
        if now < state.next_probe_monotonic:
            if (
                state.last_success_monotonic is not None
                and now - state.last_success_monotonic <= self._stale_grace
            ):
                return "ok" if state.public_status == "ok" else "stale"
            return "failed"

        self._external_attempts[plane] += 1
        started = self._monotonic()
        try:
            _verify_mcp_datasource_access(client, datasource_uid)
        except _McpReadinessError as exc:
            failure_class = exc.failure_class if exc.failure_class in {"connect", "lookup"} else "unknown"
            self._external_failures[plane][failure_class] += 1
            state.next_probe_monotonic = now + self._failure_backoff
            if (
                state.last_success_monotonic is not None
                and now - state.last_success_monotonic <= self._stale_grace
            ):
                state.public_status = "stale"
            else:
                state.public_status = "failed"
        except Exception:
            self._external_failures[plane]["unknown"] += 1
            state.next_probe_monotonic = now + self._failure_backoff
            if (
                state.last_success_monotonic is not None
                and now - state.last_success_monotonic <= self._stale_grace
            ):
                state.public_status = "stale"
            else:
                state.public_status = "failed"
        else:
            state.last_success_monotonic = now
            state.next_probe_monotonic = now + self._ttl
            state.public_status = "ok"
        finally:
            self._last_latency_seconds[plane] = max(0.0, self._monotonic() - started)
        return state.public_status

    def check(self) -> ReadinessResult:
        checks: dict[str, str] = {}
        with self._lock:
            self._check_total += 1
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

            activation_ready = (
                checks.get("metric_activation") == "ok"
                and checks.get("loki_activation") == "ok"
            )

            # Local activation/pin validation is a prerequisite for any external
            # evidence-plane work. If it cannot pass, probing Grafana cannot make
            # this process traffic-eligible and only adds avoidable network/MCP load.
            if not activation_ready:
                checks["prometheus_mcp"] = "blocked"
                checks["loki_mcp"] = "missing" if self._logs is None else "blocked"
                self._last_ready = False
                return ReadinessResult(ready=False, checks=checks)

            now = self._monotonic()
            checks["prometheus_mcp"] = self._external_status(
                "prometheus", self._metrics, self._metrics.datasource_uid, now
            )
            checks["loki_mcp"] = self._external_status(
                "loki", self._logs, self._logs.datasource_uid, now
            )

            external_ready = all(
                checks.get(name) in {"ok", "stale"}
                for name in ("prometheus_mcp", "loki_mcp")
            )
            self._last_ready = external_ready
            return ReadinessResult(ready=self._last_ready, checks=checks)

    def prometheus_metrics(self) -> str:
        """Return bounded self-observability metrics with only fixed labels."""
        with self._lock:
            lines = [
                "# HELP stageguard_readiness_ready Whether the last readiness evaluation was traffic-eligible.",
                "# TYPE stageguard_readiness_ready gauge",
                f"stageguard_readiness_ready {1 if self._last_ready else 0}",
                "# HELP stageguard_readiness_checks_total Total readiness evaluations in this process.",
                "# TYPE stageguard_readiness_checks_total counter",
                f"stageguard_readiness_checks_total {self._check_total}",
                "# HELP stageguard_readiness_external_probe_attempts_total External Grafana MCP readiness probes.",
                "# TYPE stageguard_readiness_external_probe_attempts_total counter",
            ]
            for plane in ("prometheus", "loki"):
                lines.append(
                    f'stageguard_readiness_external_probe_attempts_total{{plane="{plane}"}} '
                    f'{self._external_attempts[plane]}'
                )
            lines.extend(
                [
                    "# HELP stageguard_readiness_external_probe_failures_total External readiness failures by bounded class.",
                    "# TYPE stageguard_readiness_external_probe_failures_total counter",
                ]
            )
            for plane in ("prometheus", "loki"):
                for failure_class in ("connect", "lookup", "unknown"):
                    lines.append(
                        "stageguard_readiness_external_probe_failures_total"
                        f'{{plane="{plane}",class="{failure_class}"}} '
                        f'{self._external_failures[plane][failure_class]}'
                    )
            lines.extend(
                [
                    "# HELP stageguard_readiness_external_probe_latency_seconds Last external readiness probe latency.",
                    "# TYPE stageguard_readiness_external_probe_latency_seconds gauge",
                ]
            )
            for plane in ("prometheus", "loki"):
                lines.append(
                    f'stageguard_readiness_external_probe_latency_seconds{{plane="{plane}"}} '
                    f'{self._last_latency_seconds[plane]:.6f}'
                )
            return "\n".join(lines) + "\n"
