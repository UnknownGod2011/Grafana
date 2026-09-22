"""Release invariant: MCP smoke success reporting must not log raw telemetry."""
from __future__ import annotations

import ast
from pathlib import Path


SMOKE_PATH = Path(__file__).resolve().parents[1] / "mcp_smoke.py"


def _tree() -> ast.Module:
    return ast.parse(SMOKE_PATH.read_text(encoding="utf-8"), filename=str(SMOKE_PATH))


def _main(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
    )


def test_release_smoke_imports_safe_report_builder() -> None:
    imported = {
        alias.name
        for node in _tree().body
        if isinstance(node, ast.ImportFrom) and node.module == "mcp_smoke_reporting"
        for alias in node.names
    }
    assert {"SmokeReportError", "build_safe_smoke_report"} <= imported


def test_release_smoke_builds_report_without_query_or_evidence_payload() -> None:
    main = _main(_tree())
    calls = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_safe_smoke_report"
    ]
    assert len(calls) == 1, "release smoke must use exactly one safe report boundary"
    call = calls[0]
    keyword_names = {keyword.arg for keyword in call.keywords}
    assert keyword_names == {
        "server_info",
        "protocol_version",
        "tools",
        "datasource_uid",
        "expected_series_labels",
    }
    serialized_names = {
        node.id
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and node.func.attr == "dumps"
        for node in node.args
        if isinstance(node, ast.Name)
    }
    assert serialized_names == {"report"}, (
        "normal release success output must serialize only the sanitized report, never "
        "query_result, query, or raw MCP content"
    )


def test_release_smoke_has_no_legacy_raw_success_fields() -> None:
    main = _main(_tree())
    constants = {
        node.value
        for node in ast.walk(main)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "result_summary" not in constants
    assert "query" not in constants


def test_safe_report_failure_is_translated_to_mcp_error() -> None:
    main = _main(_tree())
    guarded = False
    for node in ast.walk(main):
        if not isinstance(node, ast.Try):
            continue
        invokes_reporter = any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "build_safe_smoke_report"
            for child in ast.walk(node)
        )
        if not invokes_reporter:
            continue
        for handler in node.handlers:
            catches_report_error = (
                isinstance(handler.type, ast.Name)
                and handler.type.id == "SmokeReportError"
            )
            raises_mcp_error = any(
                isinstance(child, ast.Raise)
                and isinstance(child.exc, ast.Call)
                and isinstance(child.exc.func, ast.Name)
                and child.exc.func.id == "McpError"
                for child in ast.walk(handler)
            )
            if catches_report_error and raises_mcp_error:
                guarded = True
                break
    assert guarded, "unsafe report metadata must fail closed through the MCP smoke error path"
