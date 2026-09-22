"""Bounded, schema-aware matching for Grafana MCP datasource discovery.

This module deliberately treats datasource identity as a field-level assertion: only a
``uid`` field may establish identity.  Human-readable names and other values must not
be allowed to satisfy a configured UID.
"""
from __future__ import annotations

import json
from typing import Any

MAX_DATASOURCE_NESTING_DEPTH = 16


def contains_datasource_uid(value: Any, expected_uid: str, *, depth: int = 0) -> bool:
    """Return True only when ``expected_uid`` occurs as the value of a ``uid`` field.

    MCP text content is commonly JSON-serialized, so strings that look like JSON are
    decoded and traversed. Traversal is bounded to avoid pathological nesting. Plain
    strings are never accepted as identity evidence, even if they equal the UID.
    """
    if depth > MAX_DATASOURCE_NESTING_DEPTH:
        return False

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped[0] not in '[{':
            return False
        try:
            decoded = json.loads(stripped)
        except (json.JSONDecodeError, RecursionError):
            return False
        return contains_datasource_uid(decoded, expected_uid, depth=depth + 1)

    if isinstance(value, dict):
        uid = value.get("uid")
        if isinstance(uid, str) and uid == expected_uid:
            return True
        return any(
            contains_datasource_uid(child, expected_uid, depth=depth + 1)
            for key, child in value.items()
            if key != "uid"
        )

    if isinstance(value, list):
        return any(contains_datasource_uid(child, expected_uid, depth=depth + 1) for child in value)

    return False
