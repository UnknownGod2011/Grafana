"""Integration regressions for the MCP smoke response-identity wrapper."""
from __future__ import annotations

import pathlib
import sys

import pytest

RUNTIME_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from mcp_smoke import McpError, _assert_response_id


def test_live_wrapper_accepts_exact_integer_response_id() -> None:
    _assert_response_id(1, 1, "initialize")


@pytest.mark.parametrize("response_id", [True, False, "1", 2])
def test_live_wrapper_rejects_nonidentical_response_id(response_id: object) -> None:
    with pytest.raises(McpError, match="unexpected response id while waiting for initialize"):
        _assert_response_id(response_id, 1, "initialize")


def test_live_wrapper_preserves_identity_failure_as_cause() -> None:
    with pytest.raises(McpError) as caught:
        _assert_response_id(True, 1, "tools/list")

    assert caught.value.__cause__ is not None
    assert type(caught.value.__cause__).__name__ == "ResponseIdentityError"
