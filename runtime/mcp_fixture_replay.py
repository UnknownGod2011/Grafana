#!/usr/bin/env python3
"""Replay a sanitized Grafana MCP capture through StageGuard's production validators.

The capture format intentionally contains only the semantic response payloads needed
for acceptance. It must not contain tokens, request headers, raw PromQL, or process
environment data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp_datasource_identity import contains_datasource_uid
from mcp_smoke_gate import PrometheusEvidenceError, assert_expected_prometheus_sample
from mcp_tool_result import ToolResultError, validated_tool_content
from mcp_tool_surface import ToolSurfaceError, validated_read_only_tool_map

MAX_FIXTURE_BYTES = 1_048_576
REQUIRED_KEYS = frozenset({"tools_list", "list_datasources", "query_prometheus", "datasource_uid", "expected_labels"})


class FixtureReplayError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON member: {key!r}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FixtureReplayError("fixture cannot be inspected") from exc
    if size <= 0 or size > MAX_FIXTURE_BYTES:
        raise FixtureReplayError(f"fixture must be between 1 and {MAX_FIXTURE_BYTES} bytes")
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise FixtureReplayError("fixture is not strict bounded UTF-8 JSON") from exc
    if type(value) is not dict:
        raise FixtureReplayError("fixture root must be a JSON object")
    if frozenset(value) != REQUIRED_KEYS:
        raise FixtureReplayError("fixture must contain exactly the documented acceptance fields")
    return value


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    datasource_uid = fixture.get("datasource_uid")
    expected_labels = fixture.get("expected_labels")
    if type(datasource_uid) is not str or not datasource_uid or len(datasource_uid) > 512:
        raise FixtureReplayError("datasource_uid must be a bounded non-empty string")
    if type(expected_labels) is not dict or not expected_labels:
        raise FixtureReplayError("expected_labels must be a non-empty JSON object")
    for key, value in expected_labels.items():
        if type(key) is not str or type(value) is not str or not key or not value or len(key) > 256 or len(value) > 512:
            raise FixtureReplayError("expected_labels must contain bounded non-empty string pairs")
    try:
        tools = validated_read_only_tool_map(fixture["tools_list"])
        datasource_content = validated_tool_content("list_datasources", fixture["list_datasources"])
        query_content = validated_tool_content("query_prometheus", fixture["query_prometheus"])
    except (ToolSurfaceError, ToolResultError) as exc:
        raise FixtureReplayError(f"fixture failed MCP structural policy: {exc}") from exc
    if not contains_datasource_uid(datasource_content, datasource_uid):
        raise FixtureReplayError("fixture does not contain the configured datasource UID")
    labels_json = json.dumps(expected_labels, separators=(",", ":"), sort_keys=True)
    try:
        matched = assert_expected_prometheus_sample(query_content, labels_json)
    except PrometheusEvidenceError as exc:
        raise FixtureReplayError(str(exc)) from exc
    return {
        "status": "pass",
        "datasource_uid": datasource_uid,
        "tool_count": len(tools),
        "matched_labels": matched,
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python runtime/mcp_fixture_replay.py <sanitized-fixture.json>", file=sys.stderr)
        return 2
    try:
        report = validate_fixture(load_fixture(Path(args[0])))
    except FixtureReplayError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
