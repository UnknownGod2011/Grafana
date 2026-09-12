from __future__ import annotations

import json
import sys
import time
import unittest

from runtime.mcp_smoke import McpError, StdioClient, _request_timeout_seconds


_RESPONDER = r'''
import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {"ok": True}}), flush=True)
'''

_SILENT = r'''
import sys
import time
for _line in sys.stdin:
    time.sleep(10)
'''


class McpSmokeTimeoutTests(unittest.TestCase):
    def test_default_and_explicit_timeout_parsing(self) -> None:
        self.assertEqual(_request_timeout_seconds(None), 15.0)
        self.assertEqual(_request_timeout_seconds(""), 15.0)
        self.assertEqual(_request_timeout_seconds(" 2.5 "), 2.5)

    def test_rejects_invalid_timeout_configuration(self) -> None:
        for raw in ("nope", "0", "-1", "nan", "inf", "121"):
            with self.subTest(raw=raw):
                with self.assertRaises(McpError):
                    _request_timeout_seconds(raw)

    def test_request_receives_matching_jsonrpc_response(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _RESPONDER],
            request_timeout_seconds=1.0,
        )
        try:
            result = client.request("ping", {"value": 1})
            self.assertEqual(result, {"ok": True})
        finally:
            client.close()

    def test_silent_server_times_out_instead_of_hanging(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _SILENT],
            request_timeout_seconds=0.1,
        )
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(McpError, "ping timed out"):
                client.request("ping")
            self.assertLess(time.monotonic() - started, 2.0)
        finally:
            client.close()

    def test_constructor_rejects_non_positive_or_non_finite_timeout(self) -> None:
        for value in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    StdioClient([sys.executable, "-c", "pass"], request_timeout_seconds=value)


if __name__ == "__main__":
    unittest.main()
