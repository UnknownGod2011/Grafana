import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_tool_surface import (
    MAX_MCP_TOOLS,
    ToolSurfaceError,
    assert_read_only_tool_surface,
    bounded_tool_map,
)


class McpToolSurfaceTests(unittest.TestCase):
    def test_accepts_surface_at_limit(self):
        tools = [{"name": f"tool_{index}", "annotations": {"readOnlyHint": True}} for index in range(MAX_MCP_TOOLS)]
        self.assertEqual(MAX_MCP_TOOLS, len(bounded_tool_map({"tools": tools})))

    def test_rejects_surface_above_limit_before_iteration(self):
        tools = [{"name": "valid"}] + [object() for _ in range(MAX_MCP_TOOLS)]
        with self.assertRaisesRegex(ToolSurfaceError, "more than"):
            bounded_tool_map({"tools": tools})

    def test_rejects_duplicate_names(self):
        with self.assertRaisesRegex(ToolSurfaceError, "duplicate tool name"):
            bounded_tool_map({"tools": [{"name": "query_prometheus"}, {"name": "query_prometheus"}]})

    def test_rejects_container_subclasses(self):
        class HostileList(list):
            pass

        with self.assertRaisesRegex(ToolSurfaceError, "non-list"):
            bounded_tool_map({"tools": HostileList()})

    def test_rejects_unsafe_name(self):
        with self.assertRaisesRegex(ToolSurfaceError, "unsafe name"):
            bounded_tool_map({"tools": [{"name": "query\u202e_prometheus"}]})

    def test_read_only_policy_accepts_required_and_additional_read_tools(self):
        tools = bounded_tool_map(
            {
                "tools": [
                    {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                    {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
                    {"name": "query_loki", "annotations": {"readOnlyHint": True}},
                ]
            }
        )
        assert_read_only_tool_surface(tools)

    def test_read_only_policy_rejects_missing_required_tool(self):
        tools = bounded_tool_map(
            {"tools": [{"name": "list_datasources", "annotations": {"readOnlyHint": True}}]}
        )
        with self.assertRaisesRegex(ToolSurfaceError, "required read tools are missing"):
            assert_read_only_tool_surface(tools)

    def test_read_only_policy_rejects_unannotated_or_write_capable_tool(self):
        tools = bounded_tool_map(
            {
                "tools": [
                    {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                    {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
                    {"name": "mutate_dashboard", "annotations": {"readOnlyHint": False}},
                ]
            }
        )
        with self.assertRaisesRegex(ToolSurfaceError, "without readOnlyHint=true"):
            assert_read_only_tool_surface(tools)

    def test_read_only_policy_rejects_annotation_dict_subclass(self):
        class HostileAnnotations(dict):
            pass

        tools = bounded_tool_map(
            {
                "tools": [
                    {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                    {"name": "query_prometheus", "annotations": HostileAnnotations(readOnlyHint=True)},
                ]
            }
        )
        with self.assertRaisesRegex(ToolSurfaceError, "without readOnlyHint=true"):
            assert_read_only_tool_surface(tools)

    def test_read_only_policy_rejects_non_boolean_truthy_hint(self):
        tools = bounded_tool_map(
            {
                "tools": [
                    {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                    {"name": "query_prometheus", "annotations": {"readOnlyHint": 1}},
                ]
            }
        )
        with self.assertRaisesRegex(ToolSurfaceError, "without readOnlyHint=true"):
            assert_read_only_tool_surface(tools)


if __name__ == "__main__":
    unittest.main()
