#!/usr/bin/env python3
"""Smoke-test the official Grafana MCP over stdio against StageGuard telemetry."""
from __future__ import annotations

import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any

from command_line import split_command

DEFAULT_COMMAND = "docker compose run --rm -T mcp"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
MAX_REQUEST_TIMEOUT_SECONDS = 120.0
MAX_STDIO_LINE_CHARS = 1_048_576
MAX_STDOUT_QUEUE_FRAMES = 16
MAX_SERVER_INFO_FIELD_CHARS = 128
MAX_TOOL_NAME_CHARS = 128
MAX_DIAGNOSTIC_CHARS = 2048
DATASOURCE_UID = os.getenv("STAGEGUARD_DATASOURCE_UID", "stageguard-prometheus")
QUERY = os.getenv(
    "STAGEGUARD_MCP_SMOKE_QUERY",
    'network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}',
)
REQUIRED_READ_TOOLS = frozenset({"list_datasources", "query_prometheus"})


class McpError(RuntimeError):
    pass


def _bounded_diagnostic(value: Any) -> str:
    """Render untrusted peer data without allowing release diagnostics to explode.

    JSON-RPC frames are already size-bounded, but a near-limit error/result can still
    make logs and operator terminals unwieldy. Keep diagnostic rendering deterministic
    and visibly mark truncation. ``repr`` also escapes embedded control characters.
    """
    rendered = repr(value)
    if len(rendered) <= MAX_DIAGNOSTIC_CHARS:
        return rendered
    omitted = len(rendered) - MAX_DIAGNOSTIC_CHARS
    return f"{rendered[:MAX_DIAGNOSTIC_CHARS]}...<truncated {omitted} chars>"


def _configured_command(raw: str | None = None) -> list[str]:
    """Return a validated stdio-only MCP launcher for the release smoke path."""
    command = os.getenv("STAGEGUARD_MCP_COMMAND", DEFAULT_COMMAND) if raw is None else raw
    try:
        return split_command(command)
    except ValueError as exc:
        raise McpError(f"invalid STAGEGUARD_MCP_COMMAND: {exc}") from exc


def _request_timeout_seconds(raw: str | None) -> float:
    if raw is None or not raw.strip():
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise McpError("STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS must be a number") from exc
    if not math.isfinite(value) or value <= 0 or value > MAX_REQUEST_TIMEOUT_SECONDS:
        raise McpError(
            "STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS must be greater than 0 and no more than "
            f"{MAX_REQUEST_TIMEOUT_SECONDS:g}"
        )
    return value


def _bounded_server_info_field(server_info: dict[str, Any], field: str) -> str:
    """Return bounded printable MCP server metadata or fail closed."""
    value = server_info.get(field)
    if not isinstance(value, str) or not value.strip():
        raise McpError("initialize returned incomplete serverInfo")
    if len(value) > MAX_SERVER_INFO_FIELD_CHARS or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise McpError(f"initialize returned unsafe serverInfo.{field}")
    return value


def _assert_initialize_result(result: dict[str, Any], requested_protocol: str) -> None:
    """Fail closed when the MCP peer negotiates an unexpected protocol contract."""
    negotiated = result.get("protocolVersion")
    if not isinstance(negotiated, str) or not negotiated.strip():
        raise McpError("initialize returned no valid protocolVersion")
    if negotiated != requested_protocol:
        raise McpError(
            "MCP protocol negotiation mismatch: "
            f"requested={requested_protocol!r}, negotiated={negotiated!r}"
        )
    capabilities = result.get("capabilities")
    if not isinstance(capabilities, dict):
        raise McpError("initialize returned malformed capabilities")
    server_info = result.get("serverInfo")
    if not isinstance(server_info, dict):
        raise McpError("initialize returned malformed serverInfo")
    _bounded_server_info_field(server_info, "name")
    _bounded_server_info_field(server_info, "version")


class StdioClient:
    def __init__(self, command: list[str], *, request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> None:
        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be a positive finite number")
        self.request_timeout_seconds = min(request_timeout_seconds, MAX_REQUEST_TIMEOUT_SECONDS)
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1)
        self._next_id = 1
        self._stdout_queue: queue.Queue[str | McpError | None] = queue.Queue(maxsize=MAX_STDOUT_QUEUE_FRAMES)
        self._stdout_overflow = threading.Event()
        self._stdout_thread = threading.Thread(target=self._read_stdout, name="stageguard-mcp-stdout", daemon=True)
        self._stdout_thread.start()

    def _offer_stdout(self, item: str | McpError | None) -> bool:
        try:
            self._stdout_queue.put_nowait(item)
            return True
        except queue.Full:
            self._stdout_overflow.set()
            return False

    def _read_stdout(self) -> None:
        stdout = self.proc.stdout
        if stdout is None:
            self._offer_stdout(None)
            return
        try:
            while True:
                line = stdout.readline(MAX_STDIO_LINE_CHARS + 1)
                if not line:
                    break
                if len(line) > MAX_STDIO_LINE_CHARS:
                    self._offer_stdout(McpError("MCP stdio response exceeded the maximum allowed JSON-RPC frame size"))
                    return
                if not self._offer_stdout(line):
                    return
        finally:
            self._offer_stdout(None)

    def send(self, message: dict[str, Any]) -> None:
        if self.proc.stdin is None:
            raise McpError("MCP stdin is unavailable")
        try:
            self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise McpError("MCP stdin closed while sending request") from exc

    def _raise_if_stdout_overflowed(self) -> None:
        if self._stdout_overflow.is_set():
            raise McpError("MCP stdio stdout exceeded the bounded pending-frame queue capacity")

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + self.request_timeout_seconds
        while True:
            self._raise_if_stdout_overflowed()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpError(f"{method} timed out after {self.request_timeout_seconds:g}s waiting for MCP response")
            try:
                line = self._stdout_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise McpError(f"{method} timed out after {self.request_timeout_seconds:g}s waiting for MCP response") from exc
            self._raise_if_stdout_overflowed()
            if isinstance(line, McpError):
                raise line
            if line is None:
                code = self.proc.poll()
                raise McpError(f"MCP process exited before {method} response (exit={code})")
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise McpError("MCP stdio stdout contained non-JSON data; stdout is reserved for JSON-RPC") from exc
            if not isinstance(message, dict):
                raise McpError("MCP stdio stdout contained a non-object JSON-RPC message")
            if message.get("jsonrpc") != "2.0":
                raise McpError("MCP stdio message did not declare jsonrpc=2.0")
            if "id" not in message:
                if isinstance(message.get("method"), str):
                    continue
                raise McpError("MCP stdio message had neither a response id nor notification method")
            if message.get("id") != request_id:
                raise McpError(f"MCP returned unexpected response id while waiting for {method}")
            if "error" in message:
                raise McpError(f"{method} failed: {_bounded_diagnostic(message['error'])}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise McpError(f"{method} returned malformed result: {_bounded_diagnostic(result)}")
            return result

    def close(self) -> None:
        if self.proc.stdin:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self._stdout_thread.join(timeout=1)
        if self.proc.stdout:
            self.proc.stdout.close()


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
        if len(name) > MAX_TOOL_NAME_CHARS or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise McpError("tools/list returned a tool with an unsafe name")
        if name in mapped:
            raise McpError(f"tools/list returned duplicate tool name: {name}")
        mapped[name] = tool
    return mapped


def _assert_read_only_tool_surface(tools: dict[str, dict[str, Any]]) -> None:
    missing = sorted(REQUIRED_READ_TOOLS - tools.keys())
    if missing:
        raise McpError(f"Required read tools are missing: {missing}; available={sorted(tools)}")
    not_explicitly_read_only = []
    for name, tool in tools.items():
        annotations = tool.get("annotations")
        if not isinstance(annotations, dict) or annotations.get("readOnlyHint") is not True:
            not_explicitly_read_only.append(name)
    if not_explicitly_read_only:
        raise McpError("MCP advertised tools without readOnlyHint=true while StageGuard is configured as an evidence-only plane: " f"{sorted(not_explicitly_read_only)}")


def _assert_tool_result(name: str, result: dict[str, Any]) -> None:
    if result.get("isError"):
        raise McpError(f"{name} returned isError=true: {_bounded_diagnostic(result.get('content'))}")


def main() -> None:
    command = _configured_command()
    request_timeout = _request_timeout_seconds(os.getenv("STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS"))
    requested_protocol = os.getenv("STAGEGUARD_MCP_PROTOCOL_VERSION", "2025-06-18")
    print("Launching official Grafana MCP smoke test:", " ".join(command))
    client = StdioClient(command, request_timeout_seconds=request_timeout)
    try:
        initialized = client.request("initialize", {"protocolVersion": requested_protocol, "capabilities": {}, "clientInfo": {"name": "stageguard-mcp-smoke", "version": "0.1.0"}})
        _assert_initialize_result(initialized, requested_protocol)
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        tools = _tool_map(client.request("tools/list"))
        _assert_read_only_tool_surface(tools)
        datasources = client.request("tools/call", {"name": "list_datasources", "arguments": {}})
        _assert_tool_result("list_datasources", datasources)
        query = client.request("tools/call", {"name": "query_prometheus", "arguments": {"datasourceUid": DATASOURCE_UID, "expr": QUERY, "queryType": "instant", "endTime": "now"}})
        _assert_tool_result("query_prometheus", query)
        print(json.dumps({"server": initialized.get("serverInfo"), "protocol_version": initialized.get("protocolVersion"), "advertised_read_only_tools": sorted(tools), "datasource_uid": DATASOURCE_UID, "query": QUERY, "result_summary": _bounded_diagnostic(query.get("content"))}, indent=2))
        print("PASS: official Grafana MCP negotiated the expected protocol, exposed only explicit read-only tools, and executed a Prometheus query through Grafana.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except (McpError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
