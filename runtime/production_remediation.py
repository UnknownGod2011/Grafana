#!/usr/bin/env python3
"""Governed production remediation policy boundary.

StageGuard owns action/target allowlisting, operation identity, retry policy, and
result metadata. A deployment-specific transport owns credentialed I/O.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from remediation import ActionResult

_OPERATION_ID_RE = re.compile(r"sg-[0-9a-f]{40}\Z")
_MAX_ALLOWLIST_ID_LENGTH = 128


def _valid_operation_id(operation_id: object) -> bool:
    """Accept only StageGuard's canonical, non-ambiguous operation identifier."""
    return type(operation_id) is str and bool(_OPERATION_ID_RE.fullmatch(operation_id))


def _valid_allowlist_identity(value: object) -> bool:
    """Require a bounded canonical identity safe to pass to provider transports."""
    if type(value) is not str or not value or len(value) > _MAX_ALLOWLIST_ID_LENGTH:
        return False
    if value != value.strip():
        return False
    return not any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)


def _bounded_number(value: object, minimum: float, maximum: float) -> bool:
    """Accept finite real configuration values while excluding bool-as-int coercion."""
    return type(value) in {int, float} and math.isfinite(value) and minimum <= value <= maximum


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


def _valid_transport_result(result: object) -> bool:
    """Validate the exact provider-result contract at runtime.

    Provider transports are an external trust boundary. Accepting subclasses here
    would allow an adapter to override field access with descriptors/properties and
    run provider-controlled code while StageGuard is validating a mutation result.
    """
    if type(result) is not TransportResult:
        return False
    if type(result.accepted) is not bool or type(result.retryable) is not bool:
        return False
    if result.status_code is not None:
        if type(result.status_code) is not int or not (100 <= result.status_code <= 599):
            return False
    if result.accepted and result.retryable:
        return False
    return True


class RemediationTransport(Protocol):
    def execute(self, request: RemediationRequest, *, timeout_seconds: float) -> TransportResult: ...


class AllowlistedProductionRemediationClient:
    """One-action, one-target production remediation adapter."""

    requires_operation_reconciliation = True

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
        try:
            execute = getattr(transport, "execute", None)
        except Exception as exc:
            raise ValueError("transport must provide a callable execute method") from exc
        if not callable(execute):
            raise ValueError("transport must provide a callable execute method")
        # Reconciliation is optional at the transport interface, but when present it
        # participates in the durable no-replay barrier. Resolve it once here just as
        # execute is resolved once: a mutable descriptor must not be able to swap the
        # reconciliation implementation between operation-state checks. Descriptor
        # faults or non-callables mean reconciliation is unavailable and fail closed.
        try:
            reconcile = getattr(transport, "reconcile", None)
        except Exception:
            reconcile = None
        if not callable(reconcile):
            reconcile = None
        if not _valid_allowlist_identity(allowed_production_id):
            raise ValueError("allowlisted production must be a canonical string of 1-128 characters without surrounding whitespace or controls")
        if not _valid_allowlist_identity(allowed_uplink):
            raise ValueError("allowlisted uplink must be a canonical string of 1-128 characters without surrounding whitespace or controls")
        if not _bounded_number(timeout_seconds, 0.1, 10.0):
            raise ValueError("timeout_seconds must be a finite number between 0.1 and 10")
        if type(max_attempts) is not int or max_attempts not in {1, 2, 3}:
            raise ValueError("max_attempts must be an integer between 1 and 3")
        if not _bounded_number(retry_delay_seconds, 0.0, 2.0):
            raise ValueError("retry_delay_seconds must be a finite number between 0 and 2")
        if not callable(sleep):
            raise ValueError("sleep must be callable")
        self._transport = transport
        # Freeze validated provider capabilities. Re-reading provider-controlled
        # descriptors during incident handling would create a check/use split.
        self._execute = execute
        self._reconcile = reconcile
        self._production_id = allowed_production_id
        self._uplink = allowed_uplink
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep

    def recover_uplink(self, production_id: str, uplink: str) -> ActionResult:
        return ActionResult(False, "idempotency context is required for production remediation")

    def recover_uplink_idempotent(self, production_id: str, uplink: str, operation_id: str) -> ActionResult:
        # Runtime callers are not trusted merely because the public API is typed.
        # Validate exact canonical strings before equality so caller-controlled
        # objects cannot execute custom __eq__ behavior inside the mutation boundary.
        if not _valid_allowlist_identity(production_id) or not _valid_allowlist_identity(uplink):
            return self._result(False, operation_id if _valid_operation_id(operation_id) else "", 0, None, "unsupported remediation target")
        if production_id != self._production_id or uplink != self._uplink:
            return self._result(False, operation_id if _valid_operation_id(operation_id) else "", 0, None, "unsupported remediation target")
        if not _valid_operation_id(operation_id):
            return self._result(False, "", 0, None, "invalid remediation operation identity")

        request = RemediationRequest(operation_id, "recover_uplink", self._production_id, self._uplink)
        last_status: int | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = self._execute(request, timeout_seconds=self._timeout_seconds)
            except (TimeoutError, OSError):
                result = TransportResult(False, None, retryable=True)
            except Exception:
                return self._result(False, operation_id, attempt, last_status, "production remediation transport fault")
            if not _valid_transport_result(result):
                return self._result(False, operation_id, attempt, last_status, "invalid production remediation transport result")
            last_status = result.status_code
            if result.accepted:
                return self._result(True, operation_id, attempt, last_status, "production remediation accepted")
            if not result.retryable or attempt >= self._max_attempts:
                return self._result(False, operation_id, attempt, last_status, "production remediation rejected or failed")
            try:
                self._sleep(self._retry_delay_seconds)
            except Exception:
                return self._result(False, operation_id, attempt, last_status, "production remediation retry scheduling fault")

        return self._result(False, operation_id, self._max_attempts, last_status, "production remediation failed")

    def reconcile_operation(self, operation_id: str) -> str:
        """Return bounded provider idempotency state without exposing provider detail."""
        if not _valid_operation_id(operation_id) or self._reconcile is None:
            return "unknown"
        try:
            state = self._reconcile(operation_id, timeout_seconds=self._timeout_seconds)
        except Exception:
            return "unknown"
        if type(state) is not str:
            return "unknown"
        return state if state in {"accepted", "not_found"} else "unknown"

    @staticmethod
    def _result(accepted: bool, operation_id: str, attempts: int, status: int | None, detail: str) -> ActionResult:
        return ActionResult(accepted, detail, {
            "adapter": "allowlisted_production",
            "operation_id": operation_id,
            "attempt_count": attempts,
            "transport_status": status,
        })