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
    return {tool.get("name"): tool for tool in tools if isinstance(tool, dict) and tool.get("name")}


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
        required = {"list_datasources", "query_prometheus"}
        missing = sorted(required - tools.keys())
        if missing:
            raise McpError(f"Required read tools are missing: {missing}; available={sorted(tools)}")
        for name in required:
            annotations = tools[name].get("annotations") or {}
            if annotations.get("readOnlyHint") is not True:
                raise McpError(f"Expected {name} to advertise readOnlyHint=true")

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
            "datasource_uid": DATASOURCE_UID,
            "query": QUERY,
            "result": query.get("content"),
        }, indent=2))
        print("PASS: official Grafana MCP executed a read-only Prometheus query through Grafana.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except (McpError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
