#!/usr/bin/env python3
"""Read-only Grafana MCP adapter for the StageGuard investigator.

This module intentionally owns only MCP transport/protocol adaptation. It does
not decide incident policy. The bounded investigator remains responsible for
which PromQL queries are allowed and how evidence is interpreted.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any

from command_line import split_command
from evidence_errors import EvidenceUnavailable
from mcp_smoke import DEFAULT_COMMAND, DATASOURCE_UID, McpError, StdioClient


class McpMetricError(McpError, EvidenceUnavailable):
    """Raised when Grafana MCP cannot provide trustworthy metric evidence."""


@dataclass(frozen=True)
class QueryTrace:
    promql: str
    latency_ms: float
    value: float | None


def _tool_payload(result: dict[str, Any]) -> Any:
    if result.get("isError"):
        raise McpMetricError("query_prometheus returned an MCP tool error")
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
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise McpMetricError("Prometheus sample value is not numeric") from exc
    if not math.isfinite(number):
        raise McpMetricError("Prometheus sample value is non-finite")
    return number


def extract_instant_value(result: dict[str, Any]) -> float | None:
    """Return exactly one finite numeric sample from an MCP query result."""
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
            raise McpMetricError("Prometheus vector sample has malformed value")
        return _coerce_number(sample[1])
    raise McpMetricError("unsupported Prometheus instant result shape")


class McpPrometheusMetricClient:
    """MetricQueryClient implementation backed by official Grafana MCP stdio."""

    def __init__(self, command: list[str] | None = None, datasource_uid: str | None = None) -> None:
        self.command = command or split_command(os.getenv("STAGEGUARD_MCP_COMMAND", DEFAULT_COMMAND))
        self.datasource_uid = datasource_uid or os.getenv("STAGEGUARD_DATASOURCE_UID", DATASOURCE_UID)
        if not self.datasource_uid.strip():
            raise ValueError("Prometheus datasource UID must be non-empty")
        self._client: StdioClient | None = None
        self.traces: list[QueryTrace] = []

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            client = StdioClient(self.command)
        except OSError as exc:
            raise McpMetricError("Grafana MCP metric process unavailable") from exc
        try:
            client.request(
                "initialize",
                {
                    "protocolVersion": os.getenv("STAGEGUARD_MCP_PROTOCOL_VERSION", "2025-06-18"),
                    "capabilities": {},
                    "clientInfo": {"name": "stageguard-investigator", "version": "0.1.0"},
                },
            )
            client.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            tools_response = client.request("tools/list")
            if not isinstance(tools_response, dict):
                raise McpMetricError("Grafana MCP tools/list response must be an object")
            tools = tools_response.get("tools", [])
            if not isinstance(tools, list):
                raise McpMetricError("Grafana MCP tools/list response is missing tools[]")
            query_tool = next(
                (tool for tool in tools if isinstance(tool, dict) and tool.get("name") == "query_prometheus"),
                None,
            )
            if query_tool is None:
                raise McpMetricError("Grafana MCP does not expose query_prometheus")
            annotations = query_tool.get("annotations") or {}
            if not isinstance(annotations, dict) or annotations.get("readOnlyHint") is not True:
                raise McpMetricError("query_prometheus does not advertise readOnlyHint=true")
        except McpMetricError:
            client.close()
            raise
        except (McpError, OSError) as exc:
            client.close()
            raise McpMetricError("Grafana MCP metric transport/protocol unavailable") from exc
        self._client = client

    def instant(self, promql: str) -> float | None:
        if not isinstance(promql, str) or not promql.strip():
            raise ValueError("PromQL must be a non-empty string")
        try:
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
            if not isinstance(result, dict):
                raise McpMetricError("query_prometheus result must be an object")
            value = extract_instant_value(result)
        except McpMetricError:
            raise
        except (McpError, OSError) as exc:
            raise McpMetricError("Grafana MCP metric transport/protocol unavailable") from exc
        self.traces.append(QueryTrace(promql, (time.perf_counter() - started) * 1000.0, value))
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
