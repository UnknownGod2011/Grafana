"""Bounded structural validation for MCP tool-call result envelopes.

This module deliberately validates only the generic MCP result envelope. Domain-specific
evidence validation (datasource identity and Prometheus sample semantics) remains in the
existing StageGuard evidence parsers.
"""
from __future__ import annotations

import math
from typing import Any

MAX_CONTENT_BLOCKS = 128
MAX_CONTAINER_ITEMS = 256
MAX_NESTING_DEPTH = 16
MAX_TEXT_CHARS = 262_144
_CONTENT_METADATA_KEYS = frozenset({"type", "mimeType", "annotations", "meta", "_meta"})


class ToolResultError(ValueError):
    """Raised when an MCP tool result violates the bounded evidence-envelope contract."""


def _meaningful(value: Any, *, depth: int = 0) -> bool:
    if depth > MAX_NESTING_DEPTH:
        return False
    if type(value) is str:
        return 0 < len(value.strip()) <= MAX_TEXT_CHARS
    if type(value) is bool:
        return False
    if type(value) is int:
        try:
            return math.isfinite(float(value))
        except OverflowError:
            return False
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is dict:
        if len(value) > MAX_CONTAINER_ITEMS:
            return False
        return any(
            type(key) is str
            and key not in _CONTENT_METADATA_KEYS
            and _meaningful(child, depth=depth + 1)
            for key, child in value.items()
        )
    if type(value) is list:
        if len(value) > MAX_CONTAINER_ITEMS:
            return False
        return any(_meaningful(child, depth=depth + 1) for child in value)
    return False


def _meaningful_content_block(item: Any) -> bool:
    if type(item) is not dict or len(item) > MAX_CONTAINER_ITEMS:
        return False
    return any(
        type(key) is str
        and key not in _CONTENT_METADATA_KEYS
        and _meaningful(value)
        for key, value in item.items()
    )


def validated_tool_content(name: str, result: Any) -> list[dict[str, Any]]:
    """Return content only after a bounded, exact-built-in MCP envelope check.

    The function fails closed for error results, hostile container subclasses, empty
    evidence, excessive block counts, or payloads whose generic semantic traversal
    would exceed StageGuard's work/size bounds.
    """
    if type(name) is not str or not name:
        raise ToolResultError("tool name must be a non-empty exact string")
    if type(result) is not dict:
        raise ToolResultError(f"{name} returned a non-object result")
    if result.get("isError") is True:
        raise ToolResultError(f"{name} returned isError=true")
    content = result.get("content")
    if type(content) is not list or not content:
        raise ToolResultError(f"{name} returned no evidence content")
    if len(content) > MAX_CONTENT_BLOCKS:
        raise ToolResultError(f"{name} returned too many evidence content blocks")
    if not any(_meaningful_content_block(item) for item in content):
        raise ToolResultError(f"{name} returned malformed, empty, or over-budget evidence content")
    return content
