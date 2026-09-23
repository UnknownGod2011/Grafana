from __future__ import annotations

import pytest

from runtime.mcp_tool_surface import ToolSurfaceError, validated_read_only_tool_map


def _tool(name: str, *, read_only: object = True) -> dict[str, object]:
    return {"name": name, "annotations": {"readOnlyHint": read_only}}


def test_atomic_validator_returns_required_read_only_tools() -> None:
    result = {
        "tools": [
            _tool("list_datasources"),
            _tool("query_prometheus"),
            _tool("list_alert_rules"),
        ]
    }

    tools = validated_read_only_tool_map(result)

    assert list(tools) == ["list_datasources", "query_prometheus", "list_alert_rules"]


@pytest.mark.parametrize(
    "result",
    [
        {"tools": [_tool("list_datasources")]},
        {"tools": [_tool("list_datasources"), _tool("query_prometheus", read_only=False)]},
        {"tools": [_tool("list_datasources"), _tool("query_prometheus", read_only=1)]},
    ],
)
def test_atomic_validator_never_returns_partially_valid_surface(result: dict[str, object]) -> None:
    with pytest.raises(ToolSurfaceError):
        validated_read_only_tool_map(result)


def test_atomic_validator_rejects_result_container_subclass() -> None:
    class ResultDict(dict):
        pass

    result = ResultDict(
        tools=[_tool("list_datasources"), _tool("query_prometheus")]
    )

    with pytest.raises(ToolSurfaceError, match="exact dictionary"):
        validated_read_only_tool_map(result)
