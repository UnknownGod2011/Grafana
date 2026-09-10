#!/usr/bin/env python3
"""Fail-closed Cloud Run entrypoint for the StageGuard incident API.

The Cloud Run artifact intentionally fixes the production-facing security
composition: IAP identity, Cloud Logging audit, non-loopback bind, and disabled
remediation. Evidence mappings/activations remain mounted configuration files.
"""
from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping

import bootstrap

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_IPV4_LIKE_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_DEFAULT_CHECKPOINT_OBJECT = "stageguard/incident-checkpoint.json"


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ValueError(f"required environment variable {name} is not set")
    return value


def _optional_bool(environ: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    """Parse an optional production feature flag without silently accepting typos."""
    raw = environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError(f"{name} must be a boolean value (true/false, 1/0, yes/no, on/off)")


def _port(environ: Mapping[str, str]) -> int:
    raw = environ.get("PORT", "8080").strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError("PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return port


def _execution_max_seconds(environ: Mapping[str, str]) -> float:
    name = "STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS"
    raw = environ.get(name, str(bootstrap.DEFAULT_MAX_REMEDIATION_EXECUTION_SECONDS)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a finite positive number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def _checkpoint_bucket(environ: Mapping[str, str]) -> str:
    bucket = environ.get("STAGEGUARD_CHECKPOINT_BUCKET", "").strip()
    if not bucket:
        return ""
    if (
        not _BUCKET_RE.fullmatch(bucket)
        or _IPV4_LIKE_RE.fullmatch(bucket)
        or ".." in bucket
        or bucket.startswith("goog")
        or "google" in bucket
    ):
        raise ValueError("STAGEGUARD_CHECKPOINT_BUCKET is not a valid bounded GCS bucket name")
    return bucket


def _checkpoint_object(environ: Mapping[str, str]) -> str:
    raw = environ.get("STAGEGUARD_CHECKPOINT_OBJECT", _DEFAULT_CHECKPOINT_OBJECT)
    name = raw.strip()
    segments = name.split("/")
    if (
        not name
        or name != raw
        or name.startswith("/")
        or name.endswith("/")
        or len(name.encode("utf-8")) > 512
        or any(segment in {"", ".", ".."} for segment in segments)
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
        or "," in name
        or "\\" in name
    ):
        raise ValueError("STAGEGUARD_CHECKPOINT_OBJECT is not a valid bounded object path")
    return name


def _checkpoint_hmac_key(environ: Mapping[str, str]) -> str:
    key = _required(environ, "STAGEGUARD_CHECKPOINT_HMAC_KEY")
    if len(key.encode("utf-8")) < 32:
        raise ValueError("STAGEGUARD_CHECKPOINT_HMAC_KEY must be at least 32 bytes")
    return key


def build_bootstrap_argv(environ: Mapping[str, str] | None = None) -> list[str]:
    """Build the immutable production bootstrap arguments from process config."""
    env = os.environ if environ is None else environ
    telemetry = _required(env, "STAGEGUARD_TELEMETRY_CONFIG")
    metric_activation = _required(env, "STAGEGUARD_METRIC_ACTIVATION")
    log_activation = _required(env, "STAGEGUARD_LOG_ACTIVATION")
    _required(env, "STAGEGUARD_IAP_AUDIENCE")

    argv = [
        "--telemetry-config", telemetry,
        "--activation", metric_activation,
        "--log-activation", log_activation,
        "--identity-mode", "iap",
        "--audit-backend", "cloud-logging",
        "--host", "0.0.0.0",
        "--port", str(_port(env)),
        "--remediation-execution-max-seconds", str(_execution_max_seconds(env)),
    ]

    checkpoint_bucket = _checkpoint_bucket(env)
    if checkpoint_bucket:
        # Bucket contents can authorize resumption of an approval, so storage write
        # permission alone must never be sufficient to forge checkpoint state.
        _checkpoint_hmac_key(env)
        checkpoint_object = _checkpoint_object(env)
        argv.extend([
            "--checkpoint-backend", "gcs",
            "--checkpoint-object", checkpoint_object,
            "--audit-integrity-policy", "require_verified",
        ])
    else:
        # Never pretend ephemeral container storage is restart durability. Without
        # a durable checkpoint there is no authenticated v3/v4 head to require.
        if env.get("STAGEGUARD_CHECKPOINT_OBJECT", "").strip():
            raise ValueError("STAGEGUARD_CHECKPOINT_OBJECT requires STAGEGUARD_CHECKPOINT_BUCKET")
        if env.get("STAGEGUARD_CHECKPOINT_HMAC_KEY", "").strip():
            raise ValueError("STAGEGUARD_CHECKPOINT_HMAC_KEY requires STAGEGUARD_CHECKPOINT_BUCKET")
        argv.extend([
            "--checkpoint-backend", "none",
            "--audit-integrity-policy", "allow_unbound_legacy",
        ])

    if _optional_bool(env, "STAGEGUARD_ENABLE_GEMINI"):
        argv.append("--enable-gemini")

    # There is intentionally no environment switch for production remediation.
    # Enabling writes requires an explicit alternate process command/deployment.
    return argv


def main() -> int:
    try:
        argv = build_bootstrap_argv()
    except ValueError as exc:
        print(f"StageGuard Cloud Run startup refused: {exc}", file=__import__("sys").stderr)
        return 2
    return bootstrap.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
