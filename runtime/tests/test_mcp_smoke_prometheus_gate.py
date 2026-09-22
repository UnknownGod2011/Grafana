"""Regression contract for the production MCP Prometheus evidence gate.

This test intentionally inspects the release-smoke module source because the gate is a
release invariant: generic MCP content validity must never be sufficient to pass a
Prometheus query.  It stays credential-free and catches accidental removal of the
semantic sample check without spawning Docker or MCP.
"""
from __future__ import annotations

import ast
from pathlib import Path


SMOKE_PATH = Path(__file__).resolve().parents[1] / "mcp_smoke.py"


def _tree() -> ast.Module:
    return ast.parse(SMOKE_PATH.read_text(encoding="utf-8"), filename=str(SMOKE_PATH))


def test_release_smoke_imports_prometheus_sample_parser() -> None:
    tree = _tree()
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "mcp_prometheus_evidence"
        for alias in node.names
    }
    assert "contains_prometheus_sample" in imported, (
        "production MCP smoke must import contains_prometheus_sample; generic MCP "
        "content validation is not sufficient release evidence"
    )


def test_release_smoke_fails_closed_when_query_has_no_prometheus_sample() -> None:
    tree = _tree()
    main = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
    )

    semantic_calls = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "contains_prometheus_sample"
    ]
    assert semantic_calls, (
        "production MCP smoke must evaluate contains_prometheus_sample after "
        "query_prometheus returns"
    )

    guarded = False
    for node in ast.walk(main):
        if not isinstance(node, ast.If):
            continue
        names = {child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)}
        calls = {
            child.func.id
            for child in ast.walk(node.test)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }
        raises_mcp_error = any(
            isinstance(child, ast.Raise)
            and isinstance(child.exc, ast.Call)
            and isinstance(child.exc.func, ast.Name)
            and child.exc.func.id == "McpError"
            for child in ast.walk(node)
        )
        if "contains_prometheus_sample" in calls and "query_result" in names and raises_mcp_error:
            guarded = True
            break

    assert guarded, (
        "contains_prometheus_sample(query_result[...]) must be a fail-closed condition "
        "that raises McpError when no genuine Prometheus sample is present"
    )
