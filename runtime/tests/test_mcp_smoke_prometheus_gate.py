"""Regression contract for the production MCP Prometheus evidence gate.

This test intentionally inspects the release-smoke module source because the gate is a
release invariant: generic MCP content validity and an unbound Prometheus sample must
never be sufficient to pass a release smoke. It stays credential-free and catches
accidental removal of expected-series binding without spawning Docker or MCP.
"""
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


def test_release_smoke_imports_bound_prometheus_gate() -> None:
    tree = _tree()
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "mcp_smoke_gate"
        for alias in node.names
    }
    assert {"PrometheusEvidenceError", "assert_expected_prometheus_sample"} <= imported, (
        "production MCP smoke must use the expected-series gate; generic MCP content "
        "validation or an unbound Prometheus sample is not sufficient release evidence"
    )


def test_release_smoke_binds_query_content_to_expected_labels_configuration() -> None:
    main = _main(_tree())
    calls = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "assert_expected_prometheus_sample"
    ]
    assert len(calls) == 1, "production MCP smoke must enforce exactly one bound sample gate"

    call = calls[0]
    names = {node.id for node in ast.walk(call) if isinstance(node, ast.Name)}
    constants = {node.value for node in ast.walk(call) if isinstance(node, ast.Constant)}
    assert "query_result" in names, "bound sample gate must inspect query_prometheus content"
    assert "STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS" in constants, (
        "bound sample gate must consume STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS"
    )


def test_release_smoke_translates_bound_gate_failure_to_mcp_error() -> None:
    main = _main(_tree())
    guarded = False
    for node in ast.walk(main):
        if not isinstance(node, ast.Try):
            continue
        invokes_gate = any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "assert_expected_prometheus_sample"
            for child in ast.walk(node)
        )
        if not invokes_gate:
            continue
        for handler in node.handlers:
            catches_evidence_error = (
                isinstance(handler.type, ast.Name)
                and handler.type.id == "PrometheusEvidenceError"
            )
            raises_mcp_error = any(
                isinstance(child, ast.Raise)
                and isinstance(child.exc, ast.Call)
                and isinstance(child.exc.func, ast.Name)
                and child.exc.func.id == "McpError"
                for child in ast.walk(handler)
            )
            if catches_evidence_error and raises_mcp_error:
                guarded = True
                break

    assert guarded, (
        "invalid expected-label configuration or mismatched telemetry must fail closed "
        "through the MCP smoke error path"
    )
