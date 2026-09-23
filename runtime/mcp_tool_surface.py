"""Bounded validation for the Grafana MCP tools/list surface.

Kept separate from process transport so the trust boundary is cheap to unit-test.
"""
from __future__ import annotations

from typing import Any

MAX_MCP_TOOLS = 256
MAX_TOOL_NAME_CHARS = 128
REQUIRED_READ_TOOLS = frozenset({"list_datasources", "query_prometheus"})
_UNSAFE_DISPLAY_CODEPOINTS = frozenset(
    {0x2028, 0x2029, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069}
)


class ToolSurfaceError(ValueError):
    """The advertised MCP tool surface is malformed or exceeds safety bounds."""


def _unsafe_name(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if codepoint < 32 or 0x7F <= codepoint <= 0x9F or codepoint in _UNSAFE_DISPLAY_CODEPOINTS:
            return True
    return False


def bounded_tool_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a unique name->tool map after enforcing deterministic work bounds."""
    if type(result) is not dict:
        raise ToolSurfaceError("tools/list result must be an exact dictionary")
    tools = result.get("tools", [])
    if type(tools) is not list:
        raise ToolSurfaceError("tools/list returned a non-list tools field")
    if len(tools) > MAX_MCP_TOOLS:
        raise ToolSurfaceError(f"tools/list advertised more than {MAX_MCP_TOOLS} tools")

    mapped: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if type(tool) is not dict:
            raise ToolSurfaceError("tools/list returned a malformed tool entry")
        name = tool.get("name")
        if type(name) is not str or not name.strip():
            raise ToolSurfaceError("tools/list returned a tool without a valid name")
        if len(name) > MAX_TOOL_NAME_CHARS or _unsafe_name(name):
            raise ToolSurfaceError("tools/list returned a tool with an unsafe name")
        if name in mapped:
            raise ToolSurfaceError(f"tools/list returned duplicate tool name: {name}")
        mapped[name] = tool
    return mapped


def assert_read_only_tool_surface(tools: dict[str, dict[str, Any]]) -> None:
    """Require StageGuard's mandatory evidence tools and explicit read-only annotations.

    The official Grafana MCP is an evidence plane, never a remediation plane. Treat
    annotations as security-relevant protocol data: only exact built-in dictionaries
    are interpreted and ``readOnlyHint`` must be the literal boolean ``True``.
    """
    if type(tools) is not dict:
        raise ToolSurfaceError("validated MCP tool map must be an exact dictionary")

    missing = sorted(REQUIRED_READ_TOOLS - tools.keys())
    if missing:
        raise ToolSurfaceError(f"required read tools are missing: {missing}")

    not_explicitly_read_only: list[str] = []
    for name, tool in tools.items():
        if type(name) is not str or type(tool) is not dict:
            raise ToolSurfaceError("validated MCP tool map contains an invalid entry")
        annotations = tool.get("annotations")
        if type(annotations) is not dict or annotations.get("readOnlyHint") is not True:
            not_explicitly_read_only.append(name)
    if not_explicitly_read_only:
        raise ToolSurfaceError(
            "MCP advertised tools without readOnlyHint=true while StageGuard is configured "
            f"as an evidence-only plane: {sorted(not_explicitly_read_only)}"
        )


def validated_read_only_tool_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate one tools/list result as a single fail-closed trust-boundary operation.

    Keeping mapping and policy application atomic prevents callers from accidentally
    consuming the advertised tool surface after structural validation but before the
    evidence-only policy has been enforced.
    """
    tools = bounded_tool_map(result)
    assert_read_only_tool_surface(tools)
    return tools
