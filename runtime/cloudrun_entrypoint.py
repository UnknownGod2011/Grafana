#!/usr/bin/env python3
"""Fail-closed Cloud Run entrypoint for the StageGuard incident API.

The Cloud Run artifact intentionally fixes the production-facing security
composition: IAP identity, Cloud Logging audit, non-loopback bind, and disabled
remediation. Evidence mappings/activations remain mounted configuration files.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

import bootstrap

_TRUE = frozenset({"1", "true", "yes", "on"})


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ValueError(f"required environment variable {name} is not set")
    return value


def _port(environ: Mapping[str, str]) -> int:
    raw = environ.get("PORT", "8080").strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError("PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return port


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
    ]

    checkpoint_bucket = env.get("STAGEGUARD_CHECKPOINT_BUCKET", "").strip()
    if checkpoint_bucket:
        # Bucket contents can authorize resumption of an approval, so storage write
        # permission alone must never be sufficient to forge checkpoint state.
        _required(env, "STAGEGUARD_CHECKPOINT_HMAC_KEY")
        argv.extend(["--checkpoint-backend", "gcs"])
        checkpoint_object = env.get("STAGEGUARD_CHECKPOINT_OBJECT", "").strip()
        if checkpoint_object:
            argv.extend(["--checkpoint-object", checkpoint_object])
    else:
        # Never pretend ephemeral container storage is restart durability.
        argv.extend(["--checkpoint-backend", "none"])

    if env.get("STAGEGUARD_ENABLE_GEMINI", "").strip().lower() in _TRUE:
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
