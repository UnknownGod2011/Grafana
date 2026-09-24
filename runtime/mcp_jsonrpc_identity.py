"""Strict JSON-RPC response identity checks for StageGuard's MCP client.

StageGuard emits monotonically increasing integer request IDs. Python considers
``True == 1`` and ``False == 0``; relying on ordinary equality would therefore
allow a JSON boolean response ID to alias an integer request ID. Keep protocol
identity type-strict at the trust boundary.
"""
from __future__ import annotations


class ResponseIdentityError(ValueError):
    """Raised when an MCP response ID cannot identify the outstanding request."""


def assert_integer_response_id(response_id: object, expected_id: int) -> None:
    """Require an exact JSON integer ID equal to StageGuard's outstanding ID.

    ``bool`` is deliberately rejected even though it subclasses ``int`` in
    Python. Structured subclasses are rejected as well so the protocol boundary
    only consumes the exact built-in representation produced by strict JSON.
    """
    if type(expected_id) is not int or expected_id < 1:
        raise ValueError("expected_id must be a positive exact integer")
    if type(response_id) is not int or response_id != expected_id:
        raise ResponseIdentityError("MCP response id did not exactly match the outstanding integer request id")
