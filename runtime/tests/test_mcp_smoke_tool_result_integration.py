import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_smoke import McpError, _assert_datasource_present, _validated_tool_content


class DictSubclass(dict):
    pass


class LiveSmokeToolResultBoundaryTests(unittest.TestCase):
    """Regression coverage for the boundary actually consumed by mcp_smoke."""

    def test_live_wrapper_accepts_meaningful_exact_builtin_content(self):
        content = _validated_tool_content(
            "query_prometheus",
            {"content": [{"type": "text", "text": "evidence"}]},
        )
        self.assertEqual([{"type": "text", "text": "evidence"}], content)

    def test_live_wrapper_translates_structural_failure_to_mcp_error(self):
        with self.assertRaisesRegex(McpError, "unsafe MCP tool result"):
            _validated_tool_content(
                "query_prometheus",
                DictSubclass(content=[{"type": "text", "text": "evidence"}]),
            )

    def test_datasource_identity_runs_after_generic_boundary(self):
        with self.assertRaisesRegex(McpError, "unsafe MCP tool result"):
            _assert_datasource_present(
                DictSubclass(content=[{"type": "text", "text": "stageguard-prometheus"}]),
                "stageguard-prometheus",
            )

    def test_datasource_identity_still_fails_closed_after_valid_envelope(self):
        with self.assertRaisesRegex(McpError, "did not return configured datasource UID"):
            _assert_datasource_present(
                {"content": [{"type": "text", "text": "other-datasource"}]},
                "stageguard-prometheus",
            )


if __name__ == "__main__":
    unittest.main()
