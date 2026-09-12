#!/usr/bin/env python3
"""Trusted operator identity boundaries for the StageGuard HTTP API.

Identity is deliberately resolved outside request bodies. Local and static
bearer providers are retained for development/small private deployments. The
Google IAP provider validates the signed ``X-Goog-IAP-JWT-Assertion`` and
never trusts the spoofable convenience identity headers as authentication.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from typing import Callable, Mapping, Protocol


IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
IAP_ISSUER = "https://cloud.google.com/iap"
MAX_IAP_ASSERTION_BYTES = 16 * 1024
MAX_IDENTITY_SUBJECT_BYTES = 512


@dataclass(frozen=True)
class OperatorIdentity:
    subject: str
    provider: str

    def __post_init__(self) -> None:
        subject = self.subject.strip()
        provider = self.provider.strip()
        if not subject:
            raise ValueError("identity subject is required")
        if not provider:
            raise ValueError("identity provider is required")
        if len(subject.encode("utf-8")) > MAX_IDENTITY_SUBJECT_BYTES:
            raise ValueError("identity subject is too large")
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "provider", provider)


class AuthenticationError(Exception):
    """Raised when a request cannot be mapped to a trusted operator.

    The HTTP layer deliberately renders ``str(exc)`` for authentication
    failures. Keep that surface bounded even when a custom identity provider
    raises ``AuthenticationError`` with provider/verifier detail: only the
    small StageGuard-owned message vocabulary below is allowed through.
    Unknown messages collapse to a generic authentication failure.
    """

    _PUBLIC_DETAILS = frozenset(
        {
            "bearer authentication required",
            "invalid bearer credential",
            "verified IAP authentication required",
            "IAP assertion is too large",
            "invalid IAP assertion",
            "IAP assertion is missing a stable subject",
            "invalid IAP operator identity",
        }
    )
    _FALLBACK_DETAIL = "authentication required"

    def __str__(self) -> str:
        detail = super().__str__()
        return detail if detail in self._PUBLIC_DETAILS else self._FALLBACK_DETAIL


class IdentityProvider(Protocol):
    """Resolve an authenticated operator from request metadata."""

    is_development_only: bool

    def authenticate(self, handler: BaseHTTPRequestHandler) -> OperatorIdentity: ...


class LocalDevelopmentIdentityProvider:
    """Fixed identity for loopback-only local development.

    This provider never consumes a user-controlled header or request field.
    The identity is configured by the process owner at server construction.
    """

    is_development_only = True

    def __init__(self, subject: str = "local-operator") -> None:
        self._identity = OperatorIdentity(subject, "local-development")

    def authenticate(self, _handler: BaseHTTPRequestHandler) -> OperatorIdentity:
        return self._identity


class StaticBearerIdentityProvider:
    """Minimal explicit bearer-token provider with constant-time token checks.

    Tokens are supplied by the host process and retained only in memory. They
    are never emitted into StageGuard API responses or audit payloads. For an
    internet-facing deployment, terminate TLS before requests reach this API.
    """

    is_development_only = False

    def __init__(self, tokens_to_subjects: Mapping[str, str]) -> None:
        configured: list[tuple[str, OperatorIdentity]] = []
        for token, subject in tokens_to_subjects.items():
            if not isinstance(token, str) or not token:
                raise ValueError("bearer tokens must be non-empty strings")
            configured.append((token, OperatorIdentity(subject, "static-bearer")))
        if not configured:
            raise ValueError("at least one bearer token is required")
        self._configured = tuple(configured)

    def authenticate(self, handler: BaseHTTPRequestHandler) -> OperatorIdentity:
        authorization = handler.headers.get("Authorization", "")
        scheme, separator, candidate = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not candidate:
            raise AuthenticationError("bearer authentication required")
        for expected, identity in self._configured:
            if hmac.compare_digest(candidate, expected):
                return identity
        raise AuthenticationError("invalid bearer credential")


IapVerifier = Callable[[str, str], Mapping[str, object]]


def _google_iap_verifier(assertion: str, audience: str) -> Mapping[str, object]:
    """Verify an IAP JWT using Google's documented Python verifier path.

    Imports are lazy so local/free StageGuard operation has no Google Auth
    dependency. ``google-auth`` is only required when IAP identity is enabled.
    """
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("google-auth is required for Google IAP identity") from exc

    return id_token.verify_token(
        assertion,
        google_requests.Request(),
        audience=audience,
        certs_url=IAP_CERTS_URL,
    )


class GoogleIapIdentityProvider:
    """Production identity provider backed by the signed Google IAP JWT.

    ``audience`` must be the exact Signed Header JWT audience for the protected
    resource (for Cloud Run, ``/projects/NUMBER/locations/REGION/services/NAME``).
    The stable JWT ``sub`` claim is used as StageGuard's operator identifier.

    Plain ``X-Goog-Authenticated-User-Id`` and ``...-Email`` headers are never
    consumed for authentication because they can be forged if IAP is bypassed.
    """

    is_development_only = False

    def __init__(self, audience: str, *, verifier: IapVerifier = _google_iap_verifier) -> None:
        normalized = audience.strip()
        if not normalized or len(normalized.encode("utf-8")) > 1024:
            raise ValueError("a bounded IAP audience is required")
        if not normalized.startswith("/projects/"):
            raise ValueError("IAP audience must be a Google resource audience")
        self._audience = normalized
        self._verifier = verifier

    @property
    def audience(self) -> str:
        return self._audience

    def authenticate(self, handler: BaseHTTPRequestHandler) -> OperatorIdentity:
        assertion = handler.headers.get("X-Goog-IAP-JWT-Assertion", "")
        if not assertion:
            raise AuthenticationError("verified IAP authentication required")
        if len(assertion.encode("utf-8")) > MAX_IAP_ASSERTION_BYTES:
            raise AuthenticationError("IAP assertion is too large")

        try:
            claims = self._verifier(assertion, self._audience)
        except Exception as exc:
            raise AuthenticationError("invalid IAP assertion") from exc
        if not isinstance(claims, Mapping):
            raise AuthenticationError("invalid IAP assertion")

        issuer = claims.get("iss")
        audience = claims.get("aud")
        subject = claims.get("sub")
        if issuer != IAP_ISSUER or audience != self._audience:
            raise AuthenticationError("invalid IAP assertion")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("IAP assertion is missing a stable subject")

        try:
            return OperatorIdentity(subject, "google-iap")
        except ValueError as exc:
            raise AuthenticationError("invalid IAP operator identity") from exc
