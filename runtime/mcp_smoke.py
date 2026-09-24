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
from mcp_datasource_identity import contains_datasource_uid
from mcp_diagnostics import safe_diagnostic
from mcp_smoke_gate import PrometheusEvidenceError, assert_expected_prometheus_sample
from mcp_smoke_reporting import SmokeReportError, build_safe_smoke_report
from mcp_tool_result import ToolResultError, validated_tool_content
from mcp_tool_surface import ToolSurfaceError, validated_read_only_tool_map

DEFAULT_COMMAND = "docker compose run --rm -T mcp"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
MAX_REQUEST_TIMEOUT_SECONDS = 120.0
MAX_STDIO_LINE_CHARS = 1_048_576
MAX_STDOUT_QUEUE_FRAMES = 16
MAX_SERVER_INFO_FIELD_CHARS = 128
MAX_CONFIG_TEXT_CHARS = 512
DATASOURCE_UID = os.getenv("STAGEGUARD_DATASOURCE_UID", "stageguard-prometheus")
QUERY = os.getenv("STAGEGUARD_MCP_SMOKE_QUERY", 'network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}')
_UNSAFE_DISPLAY_CODEPOINTS = frozenset({0x2028, 0x2029, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069})
_SENSITIVE_ARG_MARKERS = frozenset({"token", "secret", "password", "passwd", "apikey", "api-key", "authorization", "cookie", "credential", "credentials"})


class McpError(RuntimeError):
    pass


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object member: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _strict_json_rpc_loads(line: str) -> Any:
    """Decode one JSON-RPC frame without Python-specific parser extensions."""
    try:
        return json.loads(line, object_pairs_hook=_strict_json_object, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise McpError("MCP stdio stdout contained invalid or ambiguous JSON; stdout is reserved for strict JSON-RPC") from exc


def _contains_unsafe_display_char(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if codepoint < 32 or 0x7F <= codepoint <= 0x9F or codepoint in _UNSAFE_DISPLAY_CODEPOINTS:
            return True
    return False


def _bounded_config_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise McpError(f"{field} must be a non-empty string")
    if len(value) > MAX_CONFIG_TEXT_CHARS or _contains_unsafe_display_char(value):
        raise McpError(f"{field} exceeds the bounded printable configuration contract")
    return value


def _redacted_command(parts: list[str]) -> str:
    rendered: list[str] = []
    redact_next = False
    for part in parts:
        marker = part.lstrip("-\"").split("=", 1)[0].lower()
        if redact_next:
            rendered.append("<redacted>")
            redact_next = False
            continue
        if marker in _SENSITIVE_ARG_MARKERS or any(marker.startswith(f"{candidate}-") for candidate in _SENSITIVE_ARG_MARKERS):
            rendered.append(part.split("=", 1)[0] + "=<redacted>" if "=" in part else part)
            if "=" not in part:
                redact_next = True
            continue
        rendered.append(part)
    return " ".join(rendered)


def _configured_command(raw: str | None = None) -> list[str]:
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
        raise McpError(f"STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS must be greater than 0 and no more than {MAX_REQUEST_TIMEOUT_SECONDS:g}")
    return value


def _bounded_server_info_field(server_info: dict[str, Any], field: str) -> str:
    value = server_info.get(field)
    if not isinstance(value, str) or not value.strip():
        raise McpError("initialize returned incomplete serverInfo")
    if len(value) > MAX_SERVER_INFO_FIELD_CHARS or _contains_unsafe_display_char(value):
        raise McpError(f"initialize returned unsafe serverInfo.{field}")
    return value


def _assert_initialize_result(result: dict[str, Any], requested_protocol: str) -> None:
    negotiated = result.get("protocolVersion")
    if not isinstance(negotiated, str) or not negotiated.strip():
        raise McpError("initialize returned no valid protocolVersion")
    if negotiated != requested_protocol:
        raise McpError(f"MCP protocol negotiation mismatch: requested={requested_protocol!r}, negotiated={negotiated!r}")
    if not isinstance(result.get("capabilities"), dict):
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
                raise McpError(f"MCP process exited before {method} response (exit={self.proc.poll()})")
            message = _strict_json_rpc_loads(line)
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
                raise McpError(f"{method} failed: {safe_diagnostic(message['error'])}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise McpError(f"{method} returned malformed result: {safe_diagnostic(result)}")
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


def _validated_tool_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Apply the sole tools/list structural + evidence-only policy boundary."""
    try:
        return validated_read_only_tool_map(result)
    except ToolSurfaceError as exc:
        raise McpError(f"unsafe MCP tool surface: {exc}") from exc


def _validated_tool_content(name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply the sole generic tools/call result-envelope trust boundary."""
    try:
        return validated_tool_content(name, result)
    except ToolResultError as exc:
        raise McpError(f"unsafe MCP tool result: {exc}") from exc


def _assert_datasource_present(result: dict[str, Any], datasource_uid: str) -> None:
    content = _validated_tool_content("list_datasources", result)
    if not contains_datasource_uid(content, datasource_uid):
        raise McpError(f"list_datasources did not return configured datasource UID {datasource_uid!r}")


def main() -> None:
    command = _configured_command()
    request_timeout = _request_timeout_seconds(os.getenv("STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS"))
    requested_protocol = _bounded_config_text(os.getenv("STAGEGUARD_MCP_PROTOCOL_VERSION", "2025-06-18"), "STAGEGUARD_MCP_PROTOCOL_VERSION")
    datasource_uid = _bounded_config_text(DATASOURCE_UID, "STAGEGUARD_DATASOURCE_UID")
    query = _bounded_config_text(QUERY, "STAGEGUARD_MCP_SMOKE_QUERY")
    print("Launching official Grafana MCP smoke test:", _redacted_command(command))
    client = StdioClient(command, request_timeout_seconds=request_timeout)
    try:
        initialized = client.request("initialize", {"protocolVersion": requested_protocol, "capabilities": {}, "clientInfo": {"name": "stageguard-mcp-smoke", "version": "0.1.0"}})
        _assert_initialize_result(initialized, requested_protocol)
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        tools = _validated_tool_map(client.request("tools/list"))
        datasources = client.request("tools/call", {"name": "list_datasources", "arguments": {}})
        _assert_datasource_present(datasources, datasource_uid)
        query_result = client.request("tools/call", {"name": "query_prometheus", "arguments": {"datasourceUid": datasource_uid, "expr": query, "queryType": "instant", "endTime": "now"}})
        query_content = _validated_tool_content("query_prometheus", query_result)
        try:
            expected_series = assert_expected_prometheus_sample(query_content, os.getenv("STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS"))
        except PrometheusEvidenceError as exc:
            raise McpError(str(exc)) from exc
        try:
            report = build_safe_smoke_report(server_info=initialized.get("serverInfo"), protocol_version=initialized.get("protocolVersion"), tools=list(tools), datasource_uid=datasource_uid, expected_series_labels=expected_series)
        except SmokeReportError as exc:
            raise McpError(f"unsafe MCP smoke report metadata: {exc}") from exc
        print(json.dumps(report, indent=2))
        print("PASS: official Grafana MCP negotiated the expected protocol, exposed only explicit read-only tools, resolved the configured datasource UID, and returned a genuine Prometheus telemetry sample for the configured StageGuard series through Grafana.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except (McpError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
