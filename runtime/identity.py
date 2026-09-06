#!/usr/bin/env python3
"""Trusted operator identity boundaries for the StageGuard HTTP API.

Identity is deliberately resolved outside request bodies. The local provider is
only suitable for loopback development; bearer authentication is a small,
free reference provider for deployments that terminate TLS upstream or bind
behind an authenticated reverse proxy.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from typing import Mapping, Protocol


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
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "provider", provider)


class AuthenticationError(Exception):
    """Raised when a request cannot be mapped to a trusted operator."""


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
