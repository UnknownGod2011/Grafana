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
# Audit data is durable and may originate outside the current process. Bound
# parser work before splitting attacker- or corruption-controlled event names.
_MAX_RECONCILIATION_EVENT_TYPE_LENGTH = 160
_MAX_STATIC_STRING_LENGTH = 512
_MAX_STATIC_INTEGER_ABS = (1 << 63) - 1
# Static fields are policy configuration, but keeping projection work bounded
# prevents a malformed plugin/configuration from hanging an operator API request
# with an infinite iterator or creating an unexpectedly wide response.
_MAX_STATIC_FIELDS = 64


def _safe_display_string(value: str) -> bool:
    """Return whether a string is safe to place in operator-visible output.

    Reject terminal controls, line separators, and bidi formatting controls so a
    durable audit value cannot spoof timeline rows, split log records, or hide
    content when rendered in a terminal/UI. Printable Unicode remains valid.
    """
    if len(value) > _MAX_STATIC_STRING_LENGTH:
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
    """Return whether an allowlisted lifecycle value is safe to disclose.

    Field allowlists prevent accidental key disclosure, but durable audit records
    can still be corrupted or supplied by older writers. Restrict public timeline
    values to bounded JSON scalars so a trusted field name cannot smuggle nested
    provider bodies/credentials or pathological strings or integers into operator
    responses.
    """
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, str):
        return _safe_display_string(value)
    if isinstance(value, int):
        # Python integers are arbitrary precision. Bound them explicitly so a
        # corrupted durable record cannot create pathological JSON output.
        return -_MAX_STATIC_INTEGER_ABS <= value <= _MAX_STATIC_INTEGER_ABS
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def _bounded_static_fields(allowed: Iterable[str]) -> tuple[str, ...] | None:
    """Materialize a small allowlist or fail closed when policy is malformed."""
    if isinstance(allowed, (str, bytes)):
        return None
    try:
        fields = tuple(islice(iter(allowed), _MAX_STATIC_FIELDS + 1))
    except (TypeError, ValueError):
        return None
    if len(fields) > _MAX_STATIC_FIELDS or any(not isinstance(key, str) for key in fields):
        return None
    return fields


def reconciliation_timeline_payload(event_type: str, payload: Mapping[str, object]) -> dict[str, str]:
    """Return the bounded operator projection for a reconciliation audit event.

    Projection is accepted only when the event name is canonical and its encoded
    result/reason exactly match the bounded payload. This prevents a malformed,
    corrupted, oversized, or future audit event from using a trusted prefix to
    expose data under contradictory semantics. Unknown inputs fail closed to an
    empty projection.
    """
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

    result = payload.get("result")
    reason = payload.get("reason")
    if result != encoded_result or reason != encoded_reason:
        return {}
    return {"result": encoded_result, "reason": encoded_reason}


def timeline_payload(
    event_type: str,
    payload: Mapping[str, object],
    static_fields: Mapping[str, Iterable[str]],
) -> dict[str, object]:
    """Project one audit payload through StageGuard's operator disclosure policy.

    Known lifecycle events use their explicit field allowlist and bounded scalar
    values. Unknown events get no payload by default, except canonical remediation-
    reconciliation events, which are delegated to the stricter semantic projector
    above. Keeping the fallback here makes it difficult for the public timeline
    path to accidentally expose arbitrary durable audit metadata when new event
    types are introduced.
    """
    if not isinstance(event_type, str) or not isinstance(payload, Mapping):
        return {}
    if not isinstance(static_fields, Mapping):
        return {}

    allowed = static_fields.get(event_type)
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
        except (TypeError, ValueError):
            return {}

    return reconciliation_timeline_payload(event_type, payload)
