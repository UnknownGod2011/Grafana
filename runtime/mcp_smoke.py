#!/usr/bin/env python3
"""Smoke-test the official Grafana MCP over stdio against StageGuard telemetry."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any

DEFAULT_COMMAND = "docker compose run --rm -T mcp"
DATASOURCE_UID = os.getenv("STAGEGUARD_DATASOURCE_UID", "stageguard-prometheus")
QUERY = os.getenv(
    "STAGEGUARD_MCP_SMOKE_QUERY",
    'network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}',
)
REQUIRED_READ_TOOLS = frozenset({"list_datasources", "query_prometheus"})


class McpError(RuntimeError):
    pass


class StdioClient:
    def __init__(self, command: list[str]) -> None:
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
        )
        self._next_id = 1

    def send(self, message: dict[str, Any]) -> None:
        if self.proc.stdin is None:
            raise McpError("MCP stdin is unavailable")
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        if self.proc.stdout is None:
            raise McpError("MCP stdout is unavailable")
        while True:
            line = self.proc.stdout.readline()
            if not line:
                code = self.proc.poll()
                raise McpError(f"MCP process exited before response (exit={code})")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise McpError(f"{method} failed: {message['error']}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise McpError(f"{method} returned malformed result: {result!r}")
            return result

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=5)


def _tool_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tools = result.get("tools", [])
    if not isinstance(tools, list):
        raise McpError("tools/list returned a non-list tools field")

    mapped: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if not isinstance(tool, dict):
            raise McpError("tools/list returned a malformed tool entry")
        name = tool.get("name")
        if not isinstance(name, str) or not name.strip():
            raise McpError("tools/list returned a tool without a valid name")
        if name in mapped:
            raise McpError(f"tools/list returned duplicate tool name: {name}")
        mapped[name] = tool
    return mapped


def _assert_read_only_tool_surface(tools: dict[str, dict[str, Any]]) -> None:
    missing = sorted(REQUIRED_READ_TOOLS - tools.keys())
    if missing:
        raise McpError(f"Required read tools are missing: {missing}; available={sorted(tools)}")

    not_explicitly_read_only: list[str] = []
    for name, tool in tools.items():
        annotations = tool.get("annotations")
        if not isinstance(annotations, dict) or annotations.get("readOnlyHint") is not True:
            not_explicitly_read_only.append(name)

    if not_explicitly_read_only:
        raise McpError(
            "MCP advertised tools without readOnlyHint=true while StageGuard is configured "
            f"as an evidence-only plane: {sorted(not_explicitly_read_only)}"
        )


def _assert_tool_result(name: str, result: dict[str, Any]) -> None:
    if result.get("isError"):
        raise McpError(f"{name} returned isError=true: {result.get('content')}")


def main() -> None:
    command = shlex.split(os.getenv("STAGEGUARD_MCP_COMMAND", DEFAULT_COMMAND))
    print("Launching official Grafana MCP smoke test:", " ".join(command))
    client = StdioClient(command)
    try:
        initialized = client.request(
            "initialize",
            {
                "protocolVersion": os.getenv("STAGEGUARD_MCP_PROTOCOL_VERSION", "2025-06-18"),
                "capabilities": {},
                "clientInfo": {"name": "stageguard-mcp-smoke", "version": "0.1.0"},
            },
        )
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        tools = _tool_map(client.request("tools/list"))
        _assert_read_only_tool_surface(tools)

        datasources = client.request("tools/call", {"name": "list_datasources", "arguments": {}})
        _assert_tool_result("list_datasources", datasources)

        query = client.request(
            "tools/call",
            {
                "name": "query_prometheus",
                "arguments": {
                    "datasourceUid": DATASOURCE_UID,
                    "expr": QUERY,
                    "queryType": "instant",
                    "endTime": "now",
                },
            },
        )
        _assert_tool_result("query_prometheus", query)
        print(json.dumps({
            "server": initialized.get("serverInfo"),
            "advertised_read_only_tools": sorted(tools),
            "datasource_uid": DATASOURCE_UID,
            "query": QUERY,
            "result": query.get("content"),
        }, indent=2))
        print("PASS: official Grafana MCP exposed only explicit read-only tools and executed a Prometheus query through Grafana.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except (McpError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
