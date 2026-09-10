#!/usr/bin/env python3
"""Read-only official Grafana MCP adapter for bounded Loki evidence."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from command_line import split_command
from log_evidence import LogQueryResult, LogRecord
from mcp_smoke import DEFAULT_COMMAND, McpError, StdioClient

DEFAULT_LOKI_DATASOURCE_UID = "loki"


class McpLogError(McpError):
    """Raised when Grafana MCP returns an unusable Loki result."""


@dataclass(frozen=True)
class LogQueryTrace:
    logql: str
    start: str
    end: str
    limit: int
    latency_ms: float
    line_count: int
    truncated: bool


def _tool_payload(result: dict[str, Any]) -> Any:
    if result.get("isError"):
        raise McpLogError(f"query_loki_logs returned isError=true: {result.get('content')}")
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    content = result.get("content")
    if not isinstance(content, list):
        raise McpLogError("query_loki_logs result is missing MCP content")
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpLogError("query_loki_logs text content is not JSON") from exc
    raise McpLogError("query_loki_logs result contains no JSON text content")


def _string_map(value: Any, field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
        raise McpLogError(f"Loki {field} must be a string map")
    return dict(value)


def extract_log_query_result(
    result: dict[str, Any],
    *,
    requested_limit: int,
    requested_start: str,
    requested_end: str,
) -> LogQueryResult:
    """Parse the official query_loki_logs response and detect unsafe truncation.

    Newer mcp-grafana versions expose query metadata with an explicit
    resultsTruncated flag. For older compatible payloads, exactly filling the
    requested limit is conservatively treated as potentially truncated.
    """
    payload = _tool_payload(result)
    if not isinstance(payload, dict):
        raise McpLogError("query_loki_logs JSON payload must be an object")
    data = payload.get("data")
    if not isinstance(data, list):
        raise McpLogError("query_loki_logs JSON payload is missing data[]")
    if len(data) > requested_limit:
        raise McpLogError("query_loki_logs returned more lines than the requested bound")

    records: list[LogRecord] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise McpLogError("Loki data entry must be an object")
        timestamp = entry.get("timestamp")
        line = entry.get("line")
        if not isinstance(timestamp, str) or not timestamp:
            raise McpLogError("Loki log entry is missing timestamp")
        if not isinstance(line, str):
            raise McpLogError("Loki log entry is missing line")
        records.append(
            LogRecord(
                timestamp=timestamp,
                line=line,
                labels=_string_map(entry.get("labels"), "labels"),
                structured_metadata=_string_map(entry.get("structuredMetadata"), "structuredMetadata"),
                parsed=_string_map(entry.get("parsed"), "parsed"),
            )
        )

    metadata = payload.get("metadata")
    truncated: bool
    actual_start = requested_start
    actual_end = requested_end
    if metadata is None:
        truncated = len(records) == requested_limit
    else:
        if not isinstance(metadata, dict) or not isinstance(metadata.get("resultsTruncated"), bool):
            raise McpLogError("Loki metadata must contain boolean resultsTruncated")
        truncated = metadata["resultsTruncated"]
        lines_returned = metadata.get("linesReturned")
        if lines_returned is not None and lines_returned != len(records):
            raise McpLogError("Loki metadata line count disagrees with returned data")
        start_time = metadata.get("startTime")
        end_time = metadata.get("endTime")
        if start_time is not None:
            if not isinstance(start_time, str):
                raise McpLogError("Loki metadata startTime must be a string")
            actual_start = start_time
        if end_time is not None:
            if not isinstance(end_time, str):
                raise McpLogError("Loki metadata endTime must be a string")
            actual_end = end_time

    return LogQueryResult(tuple(records), truncated, actual_start, actual_end)


class McpLokiLogClient:
    """LogQueryClient backed by official Grafana MCP stdio."""

    def __init__(
        self,
        command: list[str] | None = None,
        datasource_uid: str | None = None,
    ) -> None:
        self.command = command or split_command(os.getenv("STAGEGUARD_MCP_COMMAND", DEFAULT_COMMAND))
        self.datasource_uid = datasource_uid or os.getenv(
            "STAGEGUARD_LOKI_DATASOURCE_UID", DEFAULT_LOKI_DATASOURCE_UID
        )
        if not self.datasource_uid.strip():
            raise ValueError("Loki datasource UID must be non-empty")
        self._client: StdioClient | None = None
        self.traces: list[LogQueryTrace] = []

    def connect(self) -> None:
        if self._client is not None:
            return
        client = StdioClient(self.command)
        try:
            client.request(
                "initialize",
                {
                    "protocolVersion": os.getenv("STAGEGUARD_MCP_PROTOCOL_VERSION", "2025-06-18"),
                    "capabilities": {},
                    "clientInfo": {"name": "stageguard-log-corroborator", "version": "0.1.0"},
                },
            )
            client.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            tools = client.request("tools/list").get("tools", [])
            query_tool = next(
                (tool for tool in tools if isinstance(tool, dict) and tool.get("name") == "query_loki_logs"),
                None,
            )
            if query_tool is None:
                raise McpLogError("Grafana MCP does not expose query_loki_logs")
            annotations = query_tool.get("annotations") or {}
            if annotations.get("readOnlyHint") is not True:
                raise McpLogError("query_loki_logs does not advertise readOnlyHint=true")
        except Exception:
            client.close()
            raise
        self._client = client

    def range(self, logql: str, *, start: str, end: str, limit: int) -> LogQueryResult:
        if not 1 <= limit <= 100:
            raise ValueError("Loki query limit must be between 1 and 100")
        if self._client is None:
            self.connect()
        assert self._client is not None
        started = time.perf_counter()
        result = self._client.request(
            "tools/call",
            {
                "name": "query_loki_logs",
                "arguments": {
                    "datasourceUid": self.datasource_uid,
                    "logql": logql,
                    "startRfc3339": start,
                    "endRfc3339": end,
                    "limit": limit,
                    "direction": "backward",
                    "queryType": "range",
                    "format": "full",
                },
            },
        )
        parsed = extract_log_query_result(
            result,
            requested_limit=limit,
            requested_start=start,
            requested_end=end,
        )
        self.traces.append(
            LogQueryTrace(
                logql=logql,
                start=parsed.start,
                end=parsed.end,
                limit=limit,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                line_count=len(parsed.records),
                truncated=parsed.truncated,
            )
        )
        return parsed

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "McpLokiLogClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
