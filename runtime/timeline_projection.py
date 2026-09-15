#!/usr/bin/env python3
"""Safe projection helpers for operator-visible StageGuard audit timelines.

Reconciliation audit event types intentionally encode stage/result/reason in the
name so the durable audit record remains self-describing. The operator timeline
may additionally expose the already-bounded result/reason fields, but must never
project provider operation IDs, response bodies, targets, credentials, or other
arbitrary audit metadata.
"""
from __future__ import annotations

from typing import Mapping

_RECONCILIATION_PREFIX = "remediation_reconciliation_"
_RECONCILIATION_RESULTS = frozenset({"accepted", "not_found", "unknown"})
_RECONCILIATION_REASONS = frozenset({
    "durable_dispatching",
    "legacy_unknown",
    "post_dispatch_checkpoint_regression",
    "phase_unavailable",
})


def reconciliation_timeline_payload(event_type: str, payload: Mapping[str, object]) -> dict[str, str]:
    """Return the bounded operator projection for a reconciliation audit event.

    Unknown event types or unexpected values fail closed to an empty projection.
    Values are validated independently of the event-type suffix so a malformed or
    future audit payload cannot turn the timeline endpoint into an arbitrary-data
    disclosure channel.
    """
    if not isinstance(event_type, str) or not event_type.startswith(_RECONCILIATION_PREFIX):
        return {}

    result = payload.get("result")
    reason = payload.get("reason")
    if result not in _RECONCILIATION_RESULTS or reason not in _RECONCILIATION_REASONS:
        return {}
    return {"result": str(result), "reason": str(reason)}
