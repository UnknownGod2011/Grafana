#!/usr/bin/env python3
"""Concrete HTTPS deployment transport for governed StageGuard remediation.

This module owns credentialed network I/O only. Action/target allowlisting and
retry policy remain in ``production_remediation.py``. Reconciliation is a
read-only lookup of a deployment-owned idempotency record; it never replays or
reconstructs the remediation request.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from production_remediation import RemediationRequest, TransportResult

MAX_RESPONSE_BYTES = 16 * 1024
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
_RECONCILIATION_STATES = {"accepted", "not_found"}


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Fail closed instead of replaying or forwarding credentialed requests."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _validated_https_endpoint(value: str, *, name: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https":
        raise ValueError(f"{name} must use HTTPS")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{name} must be an absolute credential-free HTTPS URL")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not contain query or fragment components")
    return value


def _default_urlopen_no_redirect(request: urllib.request.Request, *, timeout: float):
    """Open one HTTPS request with automatic redirects disabled.

    StageGuard remediation carries a write-capable bearer credential and a stable
    idempotency key. Generic HTTP redirect behavior is not an acceptable authority
    transfer for either value, so production networking uses a dedicated opener
    whose redirect handler always raises ``HTTPError``.
    """

    opener = urllib.request.build_opener(_RejectRedirects())
    return opener.open(request, timeout=timeout)


def _add_sensitive_header(request: urllib.request.Request, name: str, value: str) -> None:
    """Keep authority-bearing headers off any redirected request as defense in depth."""

    request.add_unredirected_header(name, value)


@dataclass(frozen=True)
class HttpRemediationTransport:
    """Credential-bound execution plus optional provider idempotency lookup.

    ``endpoint`` accepts immutable remediation commands. ``reconciliation_endpoint``
    is a separate deployment-owned read endpoint and is intentionally optional so
    existing local/custom deployments keep working; production uncertainty remains
    fail-closed when it is omitted.

    ``urlopen`` is an optional trusted transport seam for deterministic tests and
    custom runtime networking policy. Production callers normally leave it unset,
    in which case StageGuard uses a standard-library HTTPS opener with automatic
    redirects disabled. Callers supplying a custom opener are responsible for its
    network policy; StageGuard still marks bearer/idempotency headers as
    non-redirectable and rejects a response whose reported final URL differs from
    the configured request URL.

    The reconciliation request contains only the deterministic operation id. It
    does not contain an action, target, production id, or body that could be
    interpreted as a replay command.
    """

    endpoint: str
    bearer_token: str
    reconciliation_endpoint: str | None = None
    urlopen: Callable[..., Any] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        _validated_https_endpoint(self.endpoint, name="production remediation endpoint")
        if self.reconciliation_endpoint is not None:
            _validated_https_endpoint(
                self.reconciliation_endpoint,
                name="production remediation reconciliation endpoint",
            )
        if not self.bearer_token:
            raise ValueError("production remediation bearer credential is required")
        if any(ch in self.bearer_token for ch in "\r\n"):
            raise ValueError("production remediation bearer credential contains invalid characters")
        if self.urlopen is not None and not callable(self.urlopen):
            raise ValueError("production remediation urlopen override must be callable")

    def _open(self, request: urllib.request.Request, *, timeout_seconds: float):
        opener = self.urlopen or _default_urlopen_no_redirect
        return opener(request, timeout=timeout_seconds)

    @staticmethod
    def _response_matches_request(response: Any, request: urllib.request.Request) -> bool:
        """Reject custom-openers that silently followed a redirect when detectable."""

        geturl = getattr(response, "geturl", None)
        if not callable(geturl):
            return True
        try:
            return str(geturl()) == request.full_url
        except Exception:
            return False

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
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "stageguard-remediation/1",
            },
        )
        _add_sensitive_header(http_request, "Authorization", f"Bearer {self.bearer_token}")
        _add_sensitive_header(http_request, "Idempotency-Key", request.operation_id)

        try:
            with self._open(http_request, timeout_seconds=timeout_seconds) as response:
                status = int(response.status)
                if not self._response_matches_request(response, http_request):
                    return TransportResult(False, status, retryable=False)
                body = self._read_bounded(response)
        except urllib.error.HTTPError as exc:
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

    def reconcile(self, operation_id: str, *, timeout_seconds: float) -> str:
        """Look up provider idempotency state without replaying remediation.

        The provider contract is deliberately tiny:

        - request: ``GET <reconciliation_endpoint>/<url-encoded-operation-id>``;
        - response: exactly ``{"operation_id": "...", "state": "accepted|not_found"}``;
        - 404 maps to ``not_found`` only when the endpoint itself was configured;
        - every redirect, timeout, transport failure, auth failure, unexpected
          status, oversized body, malformed document, wrong operation echo, or
          unknown state maps to ``unknown``.

        No provider response body or transport detail escapes this method.
        """
        if self.reconciliation_endpoint is None:
            return "unknown"
        if not operation_id.startswith("sg-") or len(operation_id) != 43:
            return "unknown"

        base = self.reconciliation_endpoint.rstrip("/")
        lookup_url = f"{base}/{urllib.parse.quote(operation_id, safe='')}"
        request = urllib.request.Request(
            lookup_url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "stageguard-remediation/1",
            },
        )
        _add_sensitive_header(request, "Authorization", f"Bearer {self.bearer_token}")
        try:
            with self._open(request, timeout_seconds=timeout_seconds) as response:
                status = int(response.status)
                if not self._response_matches_request(response, request):
                    return "unknown"
                body = self._read_bounded(response)
        except urllib.error.HTTPError as exc:
            return "not_found" if int(exc.code) == 404 else "unknown"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return "unknown"

        if status < 200 or status >= 300:
            return "unknown"
        try:
            document = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "unknown"
        if not isinstance(document, dict) or set(document) != {"operation_id", "state"}:
            return "unknown"
        if document.get("operation_id") != operation_id:
            return "unknown"
        state = document.get("state")
        return state if state in _RECONCILIATION_STATES else "unknown"

    @staticmethod
    def _read_bounded(response) -> bytes:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("production remediation response exceeded size limit")
        return body
