#!/usr/bin/env python3
"""Replay a sanitized Grafana MCP capture through StageGuard's production validators.

The capture format intentionally contains only the semantic response payloads needed
for acceptance. It must not contain tokens, request headers, raw PromQL, or process
environment data.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

from mcp_datasource_identity import contains_datasource_uid
from mcp_smoke_gate import PrometheusEvidenceError, assert_expected_prometheus_sample
from mcp_tool_result import ToolResultError, validated_tool_content
from mcp_tool_surface import ToolSurfaceError, validated_read_only_tool_map

MAX_FIXTURE_BYTES = 1_048_576
MAX_EXPECTED_LABELS = 32
MAX_LABEL_NAME_BYTES = 256
MAX_LABEL_VALUE_BYTES = 512
MAX_DATASOURCE_UID_BYTES = 512
PROMETHEUS_LABEL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
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


def _bounded_utf8(value: str, limit: int) -> bool:
    """Return whether a string is non-empty and within a byte-oriented wire limit."""
    if not value:
        return False
    try:
        return len(value.encode("utf-8")) <= limit
    except UnicodeError:
        return False


def _read_bounded_fixture(path: Path) -> bytes:
    """Read a bounded capture only from a regular filesystem object.

    Open non-blocking where the platform supports it, then validate the opened
    descriptor with fstat before reading. This matters for FIFOs: a normal blocking
    open can hang *before* fstat gets a chance to reject the pipe. O_NOFOLLOW is
    also used where available so an unattended replay cannot be redirected through
    a final-component symlink. At most the configured ceiling plus one sentinel byte
    is consumed; mutable pathname metadata is never trusted for the size bound.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd: int | None = None
    try:
        fd = os.open(path, flags)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise FixtureReplayError("fixture must be a regular file")
        with os.fdopen(fd, "rb", closefd=True) as handle:
            fd = None
            raw = handle.read(MAX_FIXTURE_BYTES + 1)
    except FixtureReplayError:
        raise
    except OSError as exc:
        raise FixtureReplayError("fixture cannot be safely opened or read") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
    if not raw or len(raw) > MAX_FIXTURE_BYTES:
        raise FixtureReplayError(f"fixture must be between 1 and {MAX_FIXTURE_BYTES} bytes")
    return raw


def load_fixture(path: Path) -> dict[str, Any]:
    raw = _read_bounded_fixture(path)
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise FixtureReplayError("fixture is not strict bounded UTF-8 JSON") from exc
    if type(value) is not dict:
        raise FixtureReplayError("fixture root must be a JSON object")
    if frozenset(value) != REQUIRED_KEYS:
        raise FixtureReplayError("fixture must contain exactly the documented acceptance fields")
    return value


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    datasource_uid = fixture.get("datasource_uid")
    expected_labels = fixture.get("expected_labels")
    if type(datasource_uid) is not str or not _bounded_utf8(datasource_uid, MAX_DATASOURCE_UID_BYTES):
        raise FixtureReplayError("datasource_uid must be a bounded non-empty string")
    if type(expected_labels) is not dict or not expected_labels or len(expected_labels) > MAX_EXPECTED_LABELS:
        raise FixtureReplayError(f"expected_labels must contain between 1 and {MAX_EXPECTED_LABELS} labels")
    for key, value in expected_labels.items():
        if (
            type(key) is not str
            or type(value) is not str
            or PROMETHEUS_LABEL_NAME.fullmatch(key) is None
            or not _bounded_utf8(key, MAX_LABEL_NAME_BYTES)
            or not _bounded_utf8(value, MAX_LABEL_VALUE_BYTES)
        ):
            raise FixtureReplayError("expected_labels must contain valid bounded Prometheus label names and non-empty string values")
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

    # Success output is intentionally metadata-only. The fixture may contain
    # production identifiers in label values; proving the expected labels matched
    # does not require echoing those values into logs or CI output.
    matched_label_names = sorted(key for key in expected_labels if key in matched)
    return {
        "status": "pass",
        "datasource_uid": datasource_uid,
        "tool_count": len(tools),
        "matched_label_names": matched_label_names,
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
