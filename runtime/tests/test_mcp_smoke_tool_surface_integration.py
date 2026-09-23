import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_smoke import McpError, _validated_tool_map


class McpSmokeToolSurfaceIntegrationTests(unittest.TestCase):
    @staticmethod
    def _tool(name: str, *, read_only=True):
        return {"name": name, "annotations": {"readOnlyHint": read_only}}

    def test_live_boundary_accepts_required_read_only_surface(self):
        result = {
            "tools": [
                self._tool("list_datasources"),
                self._tool("query_prometheus"),
                self._tool("list_alert_rules"),
            ]
        }
        mapped = _validated_tool_map(result)
        self.assertEqual(
            {"list_datasources", "query_prometheus", "list_alert_rules"},
            set(mapped),
        )

    def test_live_boundary_translates_policy_failure_to_mcp_error(self):
        result = {
            "tools": [
                self._tool("list_datasources"),
                self._tool("query_prometheus"),
                self._tool("write_dashboard", read_only=False),
            ]
        }
        with self.assertRaisesRegex(McpError, "unsafe MCP tool surface"):
            _validated_tool_map(result)

    def test_live_boundary_translates_structural_failure_to_mcp_error(self):
        with self.assertRaisesRegex(McpError, "unsafe MCP tool surface"):
            _validated_tool_map({"tools": "not-a-list"})


if __name__ == "__main__":
    unittest.main()
