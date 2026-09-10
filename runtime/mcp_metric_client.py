#!/usr/bin/env python3
"""Read-only Grafana MCP adapter for the StageGuard investigator.

This module intentionally owns only MCP transport/protocol adaptation. It does
not decide incident policy. The bounded investigator remains responsible for
which PromQL queries are allowed and how evidence is interpreted.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from command_line import split_command
from mcp_smoke import DEFAULT_COMMAND, DATASOURCE_UID, McpError, StdioClient


class McpMetricError(McpError):
    """Raised when Grafana MCP returns an unusable metric result."""


@dataclass(frozen=True)
class QueryTrace:
    promql: str
    latency_ms: float
    value: float | None


def _tool_payload(result: dict[str, Any]) -> Any:
    """Extract the JSON payload returned by a successful MCP tool call.

    mcp-grafana v1.1.0 serializes ordinary tool return values as JSON text in
    CallToolResult.content. We also accept structuredContent defensively so the
    adapter remains compatible with servers that expose the same payload using
    newer MCP result conventions.
    """
    if result.get("isError"):
        raise McpMetricError(f"query_prometheus returned isError=true: {result.get('content')}")

    structured = result.get("structuredContent")
    if structured is not None:
        return structured

    content = result.get("content")
    if not isinstance(content, list):
        raise McpMetricError("query_prometheus result is missing MCP content")

    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpMetricError("query_prometheus text content is not JSON") from exc

    raise McpMetricError("query_prometheus result contains no JSON text content")


def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise McpMetricError(f"Prometheus sample value is not numeric: {value!r}") from exc


def extract_instant_value(result: dict[str, Any]) -> float | None:
    """Return exactly one numeric sample from an MCP query_prometheus result.

    Prometheus model.Value JSON encodes vectors as a list of sample objects and
    scalars as ``[timestamp, value]``. Empty vectors are legitimate missing
    evidence and therefore map to ``None``. Multiple vector samples are rejected
    rather than guessed because StageGuard's bounded queries are expected to
    resolve to one scalar observation each.
    """
    payload = _tool_payload(result)
    if not isinstance(payload, dict) or "data" not in payload:
        raise McpMetricError("query_prometheus JSON payload is missing data")

    data = payload["data"]
    if data is None or data == []:
        return None

    if isinstance(data, list) and len(data) == 2 and not isinstance(data[0], dict):
        return _coerce_number(data[1])

    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        if len(data) == 0:
            return None
        if len(data) != 1:
            raise McpMetricError(
                f"bounded instant query returned {len(data)} series; expected exactly one"
            )
        sample = data[0].get("value")
        if not isinstance(sample, list) or len(sample) != 2:
            raise McpMetricError(f"Prometheus vector sample has malformed value: {sample!r}")
        return _coerce_number(sample[1])

    raise McpMetricError(f"unsupported Prometheus instant result shape: {data!r}")


class McpPrometheusMetricClient:
    """MetricQueryClient implementation backed by official Grafana MCP stdio."""

    def __init__(
        self,
        command: list[str] | None = None,
        datasource_uid: str | None = None,
    ) -> None:
        self.command = command or split_command(os.getenv("STAGEGUARD_MCP_COMMAND", DEFAULT_COMMAND))
        self.datasource_uid = datasource_uid or os.getenv(
            "STAGEGUARD_DATASOURCE_UID", DATASOURCE_UID
        )
        self._client: StdioClient | None = None
        self.traces: list[QueryTrace] = []

    def connect(self) -> None:
        if self._client is not None:
            return
        client = StdioClient(self.command)
        try:
            client.request(
                "initialize",
                {
                    "protocolVersion": os.getenv(
                        "STAGEGUARD_MCP_PROTOCOL_VERSION", "2025-06-18"
                    ),
                    "capabilities": {},
                    "clientInfo": {"name": "stageguard-investigator", "version": "0.1.0"},
                },
            )
            client.send(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
            )
            tools = client.request("tools/list").get("tools", [])
            query_tool = next(
                (
                    tool
                    for tool in tools
                    if isinstance(tool, dict) and tool.get("name") == "query_prometheus"
                ),
                None,
            )
            if query_tool is None:
                raise McpMetricError("Grafana MCP does not expose query_prometheus")
            annotations = query_tool.get("annotations") or {}
            if annotations.get("readOnlyHint") is not True:
                raise McpMetricError("query_prometheus does not advertise readOnlyHint=true")
        except Exception:
            client.close()
            raise
        self._client = client

    def instant(self, promql: str) -> float | None:
        if self._client is None:
            self.connect()
        assert self._client is not None

        started = time.perf_counter()
        result = self._client.request(
            "tools/call",
            {
                "name": "query_prometheus",
                "arguments": {
                    "datasourceUid": self.datasource_uid,
                    "expr": promql,
                    "queryType": "instant",
                    "endTime": "now",
                },
            },
        )
        value = extract_instant_value(result)
        self.traces.append(
            QueryTrace(
                promql=promql,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                value=value,
            )
        )
        return value

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "McpPrometheusMetricClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
