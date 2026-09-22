"""Source invariant for the MCP smoke's untrusted failure-diagnostic boundary."""
from __future__ import annotations

import ast
from pathlib import Path

SMOKE_PATH = Path(__file__).resolve().parents[1] / "mcp_smoke.py"


def _source() -> str:
    return SMOKE_PATH.read_text(encoding="utf-8")


def test_smoke_imports_secret_aware_diagnostic_boundary() -> None:
    source = _source()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "mcp_diagnostics"
        for alias in node.names
    }
    assert "safe_diagnostic" in imports


def test_legacy_raw_repr_diagnostic_helper_is_absent() -> None:
    source = _source()
    tree = ast.parse(source)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "_bounded_diagnostic" not in function_names
    assert "repr(" not in source


def test_untrusted_jsonrpc_and_tool_error_material_crosses_safe_diagnostic() -> None:
    source = _source()
    assert "safe_diagnostic(message['error'])" in source
    assert "safe_diagnostic(result)" in source
    assert "safe_diagnostic(result.get('content'))" in source


def test_failure_output_does_not_serialize_upstream_payloads_directly() -> None:
    source = _source()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "print":
            continue
        rendered = ast.unparse(node)
        if "file=sys.stderr" in rendered:
            assert "message[" not in rendered
            assert "result.get('content')" not in rendered
            assert "query_result" not in rendered
