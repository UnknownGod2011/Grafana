#!/usr/bin/env python3
"""Concrete HTTPS deployment transport for governed StageGuard remediation.

This module owns credentialed network I/O only. Action/target allowlisting and
retry policy remain in ``production_remediation.py``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from production_remediation import RemediationRequest, TransportResult

MAX_RESPONSE_BYTES = 16 * 1024
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class HttpRemediationTransport:
    """POST one immutable remediation request to one deployment-owned HTTPS URL.

    The bearer credential and endpoint are constructor-owned process settings;
    neither can be supplied by an incident/API caller. The server must echo the
    operation ID so StageGuard can reject a response for the wrong idempotency key.
    """

    endpoint: str
    bearer_token: str

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlparse(self.endpoint)
        if parsed.scheme != "https":
            raise ValueError("production remediation endpoint must use HTTPS")
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("production remediation endpoint must be an absolute credential-free HTTPS URL")
        if parsed.query or parsed.fragment:
            raise ValueError("production remediation endpoint must not contain query or fragment components")
        if not self.bearer_token:
            raise ValueError("production remediation bearer credential is required")
        if any(ch in self.bearer_token for ch in "\r\n"):
            raise ValueError("production remediation bearer credential contains invalid characters")

    def execute(self, request: RemediationRequest, *, timeout_seconds: float) -> TransportResult:
        payload = json.dumps(
            {
                "operation_id": request.operation_id,
                "action": request.action,
                "production_id": request.production_id,
                "target": request.target,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        http_request = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Idempotency-Key": request.operation_id,
                "User-Agent": "stageguard-remediation/1",
            },
        )

        try:
            with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
                status = int(response.status)
                body = self._read_bounded(response)
        except urllib.error.HTTPError as exc:
            # Never include response bodies, endpoint values, headers, or tokens in
            # returned metadata. The policy layer only needs retryability + status.
            status = int(exc.code)
            return TransportResult(False, status, retryable=status in _RETRYABLE_STATUS)
        except (urllib.error.URLError, TimeoutError, OSError):
            return TransportResult(False, None, retryable=True)

        if status < 200 or status >= 300:
            return TransportResult(False, status, retryable=status in _RETRYABLE_STATUS)

        try:
            document = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return TransportResult(False, status, retryable=False)
        if not isinstance(document, dict) or set(document) != {"accepted", "operation_id"}:
            return TransportResult(False, status, retryable=False)
        if type(document["accepted"]) is not bool or document["operation_id"] != request.operation_id:
            return TransportResult(False, status, retryable=False)
        return TransportResult(document["accepted"], status, retryable=False)

    @staticmethod
    def _read_bounded(response) -> bytes:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("production remediation response exceeded size limit")
        return body
