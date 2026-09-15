#!/usr/bin/env python3
"""Safe projection helpers for operator-visible StageGuard audit timelines.

Reconciliation audit event types intentionally encode stage/result/reason in the
name so the durable audit record remains self-describing. The operator timeline
may additionally expose the already-bounded result/reason fields, but must never
project provider operation IDs, response bodies, targets, credentials, or other
arbitrary audit metadata.
"""
from __future__ import annotations

from collections.abc import Iterable
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

    Known lifecycle events use their explicit field allowlist. Unknown events get
    no payload by default, except canonical remediation-reconciliation events,
    which are delegated to the stricter semantic projector above. Keeping the
    fallback here makes it difficult for the public timeline path to accidentally
    expose arbitrary durable audit metadata when new event types are introduced.
    """
    if not isinstance(event_type, str) or not isinstance(payload, Mapping):
        return {}
    if not isinstance(static_fields, Mapping):
        return {}

    allowed = static_fields.get(event_type)
    if allowed is not None:
        try:
            return {key: payload[key] for key in allowed if isinstance(key, str) and key in payload}
        except (TypeError, ValueError):
            return {}

    return reconciliation_timeline_payload(event_type, payload)
