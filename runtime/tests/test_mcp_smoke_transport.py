import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_smoke import DEFAULT_COMMAND, McpError, _configured_command, _strict_json_rpc_loads


class McpSmokeTransportTests(unittest.TestCase):
    def test_default_compose_launcher_remains_allowed(self):
        self.assertEqual(
            ["docker", "compose", "run", "--rm", "-T", "mcp"],
            _configured_command(DEFAULT_COMMAND),
        )

    def test_native_binary_stdio_default_remains_allowed(self):
        self.assertEqual(
            ["mcp-grafana", "--disable-write"],
            _configured_command("mcp-grafana --disable-write"),
        )

    def test_explicit_stdio_transport_remains_allowed(self):
        command = "docker run --rm grafana/mcp-grafana:1.4.1 -t stdio"
        self.assertEqual(
            ["docker", "run", "--rm", "grafana/mcp-grafana:1.4.1", "-t", "stdio"],
            _configured_command(command),
        )

    def test_direct_official_docker_image_without_stdio_fails_closed(self):
        with self.assertRaisesRegex(McpError, "explicitly set -t stdio"):
            _configured_command("docker run --rm grafana/mcp-grafana:1.4.1")

    def test_network_transport_overrides_fail_before_spawn(self):
        commands = (
            "mcp-grafana -t sse",
            "mcp-grafana --transport sse",
            "mcp-grafana -t=streamable-http",
            "mcp-grafana --transport=streamable-http",
            "docker run --rm grafana/mcp-grafana:1.4.1 --transport sse",
        )
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaisesRegex(McpError, "stdio transport"):
                    _configured_command(command)

    def test_unknown_transport_fails_closed(self):
        with self.assertRaisesRegex(McpError, "requires Grafana MCP stdio transport"):
            _configured_command("mcp-grafana --transport websocket")

    def test_malformed_override_is_reported_as_bounded_mcp_error(self):
        with self.assertRaisesRegex(McpError, "invalid STAGEGUARD_MCP_COMMAND"):
            _configured_command('docker run "unterminated')

    def test_environment_override_uses_same_validation_boundary(self):
        with mock.patch.dict(
            os.environ,
            {"STAGEGUARD_MCP_COMMAND": "mcp-grafana --transport streamable-http"},
            clear=False,
        ):
            with self.assertRaisesRegex(McpError, "network transport is forbidden"):
                _configured_command()

    def test_strict_json_rpc_accepts_unique_standard_json(self):
        self.assertEqual(
            {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}},
            _strict_json_rpc_loads('{"jsonrpc":"2.0","id":1,"result":{"ok":true}}'),
        )

    def test_strict_json_rpc_rejects_duplicate_security_critical_member(self):
        with self.assertRaisesRegex(McpError, "invalid or ambiguous JSON"):
            _strict_json_rpc_loads('{"jsonrpc":"2.0","id":1,"id":2,"result":{}}')

    def test_strict_json_rpc_rejects_duplicate_nested_member(self):
        with self.assertRaisesRegex(McpError, "invalid or ambiguous JSON"):
            _strict_json_rpc_loads('{"jsonrpc":"2.0","id":1,"result":{"content":[],"content":[1]}}')

    def test_strict_json_rpc_rejects_python_only_numeric_constants(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                with self.assertRaisesRegex(McpError, "invalid or ambiguous JSON"):
                    _strict_json_rpc_loads('{"jsonrpc":"2.0","id":1,"result":{"value":' + constant + '}}')


if __name__ == "__main__":
    unittest.main()
