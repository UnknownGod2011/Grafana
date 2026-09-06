#!/usr/bin/env python3
"""Governed production remediation policy boundary.

StageGuard owns action/target allowlisting, operation identity, retry policy, and
result metadata. A deployment-specific transport owns credentialed I/O.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol

from remediation import ActionResult


@dataclass(frozen=True)
class RemediationRequest:
    operation_id: str
    action: str
    production_id: str
    target: str


@dataclass(frozen=True)
class TransportResult:
    accepted: bool
    status_code: int | None
    retryable: bool = False


class RemediationTransport(Protocol):
    def execute(self, request: RemediationRequest, *, timeout_seconds: float) -> TransportResult: ...


class AllowlistedProductionRemediationClient:
    """One-action, one-target production remediation adapter.

    No URL, action, or target can be supplied by an incident/API caller. The
    deployment injects a transport already bound to its credential and endpoint.
    Retries are bounded and always reuse the same operation identity.
    """

    def __init__(
        self,
        transport: RemediationTransport,
        *,
        allowed_production_id: str,
        allowed_uplink: str,
        timeout_seconds: float = 3.0,
        max_attempts: int = 2,
        retry_delay_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not allowed_production_id.strip() or not allowed_uplink.strip():
            raise ValueError("allowlisted production and uplink are required")
        if not (0.1 <= timeout_seconds <= 10.0):
            raise ValueError("timeout_seconds must be between 0.1 and 10")
        if max_attempts not in {1, 2, 3}:
            raise ValueError("max_attempts must be between 1 and 3")
        if not (0.0 <= retry_delay_seconds <= 2.0):
            raise ValueError("retry_delay_seconds must be between 0 and 2")
        self._transport = transport
        self._production_id = allowed_production_id
        self._uplink = allowed_uplink
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep

    def recover_uplink(self, production_id: str, uplink: str) -> ActionResult:
        return ActionResult(False, "idempotency context is required for production remediation")

    def recover_uplink_idempotent(self, production_id: str, uplink: str, operation_id: str) -> ActionResult:
        if production_id != self._production_id or uplink != self._uplink:
            return self._result(False, operation_id, 0, None, "unsupported remediation target")
        if not operation_id.startswith("sg-") or len(operation_id) != 43:
            return self._result(False, operation_id, 0, None, "invalid remediation operation identity")

        request = RemediationRequest(operation_id, "recover_uplink", self._production_id, self._uplink)
        last_status: int | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = self._transport.execute(request, timeout_seconds=self._timeout_seconds)
            except (TimeoutError, OSError):
                result = TransportResult(False, None, retryable=True)
            last_status = result.status_code
            if result.accepted:
                return self._result(True, operation_id, attempt, last_status, "production remediation accepted")
            if not result.retryable or attempt >= self._max_attempts:
                return self._result(False, operation_id, attempt, last_status, "production remediation rejected or failed")
            self._sleep(self._retry_delay_seconds)

        return self._result(False, operation_id, self._max_attempts, last_status, "production remediation failed")

    @staticmethod
    def _result(accepted: bool, operation_id: str, attempts: int, status: int | None, detail: str) -> ActionResult:
        return ActionResult(accepted, detail, {
            "adapter": "allowlisted_production",
            "operation_id": operation_id,
            "attempt_count": attempts,
            "transport_status": status,
        })
