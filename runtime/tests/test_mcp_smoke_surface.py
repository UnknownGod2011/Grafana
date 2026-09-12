from __future__ import annotations

import unittest

from runtime.mcp_smoke import McpError, _assert_read_only_tool_surface, _tool_map


class McpSmokeSurfaceTests(unittest.TestCase):
    def test_accepts_explicitly_read_only_required_and_optional_tools(self) -> None:
        tools = _tool_map(
            {
                "tools": [
                    {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                    {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
                    {"name": "query_loki", "annotations": {"readOnlyHint": True}},
                ]
            }
        )

        _assert_read_only_tool_surface(tools)

    def test_rejects_missing_required_read_tool(self) -> None:
        tools = _tool_map(
            {"tools": [{"name": "list_datasources", "annotations": {"readOnlyHint": True}}]}
        )

        with self.assertRaisesRegex(McpError, "Required read tools are missing"):
            _assert_read_only_tool_surface(tools)

    def test_rejects_write_capable_or_unannotated_advertised_tool(self) -> None:
        for annotations in ({"readOnlyHint": False}, {}, None):
            with self.subTest(annotations=annotations):
                tools = _tool_map(
                    {
                        "tools": [
                            {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                            {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
                            {"name": "unexpected_tool", "annotations": annotations},
                        ]
                    }
                )

                with self.assertRaisesRegex(McpError, "without readOnlyHint=true"):
                    _assert_read_only_tool_surface(tools)

    def test_rejects_malformed_tools_field(self) -> None:
        with self.assertRaisesRegex(McpError, "non-list tools field"):
            _tool_map({"tools": {"name": "query_prometheus"}})

    def test_rejects_malformed_tool_entry(self) -> None:
        with self.assertRaisesRegex(McpError, "malformed tool entry"):
            _tool_map({"tools": ["query_prometheus"]})

    def test_rejects_missing_or_blank_tool_name(self) -> None:
        for entry in ({}, {"name": ""}, {"name": "   "}, {"name": 7}):
            with self.subTest(entry=entry):
                with self.assertRaisesRegex(McpError, "without a valid name"):
                    _tool_map({"tools": [entry]})

    def test_rejects_duplicate_tool_names(self) -> None:
        with self.assertRaisesRegex(McpError, "duplicate tool name"):
            _tool_map(
                {
                    "tools": [
                        {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
                        {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
