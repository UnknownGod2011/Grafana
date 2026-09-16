#!/usr/bin/env python3
"""Safe projection helpers for operator-visible StageGuard audit timelines.

Reconciliation audit event types intentionally encode stage/result/reason in the
name so the durable audit record remains self-describing. The operator timeline
may additionally expose the already-bounded result/reason fields, but must never
project provider operation IDs, response bodies, targets, credentials, or other
arbitrary audit metadata.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import islice
from typing import Mapping

_RECONCILIATION_PREFIX = "remediation_reconciliation_"
_RECONCILIATION_STAGES = frozenset({"attempt", "recovered"})
_RECONCILIATION_RESULTS = frozenset({"accepted", "not_found", "unknown"})
_RECONCILIATION_REASONS = frozenset({
    "durable_dispatching",
    "legacy_unknown",
    "post_dispatch_checkpoint_regression",
    "phase_unavailable",
})
_MAX_RECONCILIATION_EVENT_TYPE_LENGTH = 160
_MAX_STATIC_STRING_LENGTH = 512
_MAX_STATIC_FIELD_NAME_LENGTH = 128
_MAX_STATIC_INTEGER_ABS = (1 << 63) - 1
_MAX_STATIC_FIELDS = 64


def _safe_display_string(value: str, *, max_length: int = _MAX_STATIC_STRING_LENGTH) -> bool:
    if len(value) > max_length:
        return False
    for char in value:
        codepoint = ord(char)
        if codepoint < 0x20 or codepoint == 0x7F:
            return False
        if 0x80 <= codepoint <= 0x9F:
            return False
        if codepoint in {0x2028, 0x2029}:
            return False
        if 0x202A <= codepoint <= 0x202E or 0x2066 <= codepoint <= 0x2069:
            return False
    return True


def _safe_static_value(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, str):
        return _safe_display_string(value)
    if isinstance(value, int):
        return -_MAX_STATIC_INTEGER_ABS <= value <= _MAX_STATIC_INTEGER_ABS
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def _bounded_static_fields(allowed: Iterable[str]) -> tuple[str, ...] | None:
    """Materialize a small, display-safe allowlist or fail closed when malformed."""
    if isinstance(allowed, (str, bytes)):
        return None
    try:
        fields = tuple(islice(iter(allowed), _MAX_STATIC_FIELDS + 1))
    except Exception:
        return None
    if len(fields) > _MAX_STATIC_FIELDS:
        return None
    if any(
        not isinstance(key, str)
        or not key
        or not _safe_display_string(key, max_length=_MAX_STATIC_FIELD_NAME_LENGTH)
        for key in fields
    ):
        return None
    return fields


def reconciliation_timeline_payload(event_type: str, payload: Mapping[str, object]) -> dict[str, str]:
    """Return the bounded operator projection for a reconciliation audit event."""
    if (
        not isinstance(event_type, str)
        or len(event_type) > _MAX_RECONCILIATION_EVENT_TYPE_LENGTH
        or not event_type.startswith(_RECONCILIATION_PREFIX)
    ):
        return {}
    if not isinstance(payload, Mapping):
        return {}

    suffix = event_type[len(_RECONCILIATION_PREFIX):]
    parts = suffix.split(".")
    if len(parts) != 3:
        return {}
    stage, encoded_result, encoded_reason = parts
    if stage not in _RECONCILIATION_STAGES:
        return {}
    if encoded_result not in _RECONCILIATION_RESULTS or encoded_reason not in _RECONCILIATION_REASONS:
        return {}

    # Durable mappings may come from adapters or older persistence layers. Treat
    # mapping access itself as untrusted: a custom Mapping can raise while reading
    # an otherwise canonical event and must not turn the public timeline into 500.
    try:
        result = payload.get("result")
        reason = payload.get("reason")
    except Exception:
        return {}
    if result != encoded_result or reason != encoded_reason:
        return {}
    return {"result": encoded_result, "reason": encoded_reason}


def timeline_payload(
    event_type: str,
    payload: Mapping[str, object],
    static_fields: Mapping[str, Iterable[str]],
) -> dict[str, object]:
    """Project one audit payload through StageGuard's operator disclosure policy."""
    if not isinstance(event_type, str) or not isinstance(payload, Mapping):
        return {}
    if not isinstance(static_fields, Mapping):
        return {}

    # Policy lookup can itself be implemented by an extension Mapping. Fail
    # closed on ordinary lookup failures rather than leaking a partial timeline
    # or surfacing an operator-visible server error.
    try:
        allowed = static_fields.get(event_type)
    except Exception:
        return {}
    if allowed is not None:
        fields = _bounded_static_fields(allowed)
        if fields is None:
            return {}
        try:
            return {
                key: payload[key]
                for key in fields
                if key in payload and _safe_static_value(payload[key])
            }
        except Exception:
            return {}

    return reconciliation_timeline_payload(event_type, payload)
