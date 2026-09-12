from __future__ import annotations

import json
import sys
import time
import unittest

from runtime.mcp_smoke import (
    MAX_STDIO_LINE_CHARS,
    MAX_STDOUT_QUEUE_FRAMES,
    McpError,
    StdioClient,
    _request_timeout_seconds,
)


_RESPONDER = r'''
import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {"ok": True}}), flush=True)
'''

_NOTIFICATION_THEN_RESPONSE = r'''
import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    print(json.dumps({"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 1}}), flush=True)
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {"ok": True}}), flush=True)
'''

_DIRTY_STDOUT = r'''
import sys
for _line in sys.stdin:
    print("unexpected log line on stdout", flush=True)
    break
'''

_WRONG_ID = r'''
import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"] + 1, "result": {"ok": True}}), flush=True)
    break
'''

_MALFORMED_ENVELOPE = r'''
import json
import sys
for _line in sys.stdin:
    print(json.dumps({"jsonrpc": "1.0", "id": 1, "result": {"ok": True}}), flush=True)
    break
'''

_SILENT = r'''
import sys
import time
for _line in sys.stdin:
    time.sleep(10)
'''


def _oversized_stdout_script() -> str:
    return f'''
import sys
for _line in sys.stdin:
    sys.stdout.write("x" * {MAX_STDIO_LINE_CHARS + 1})
    sys.stdout.flush()
    break
'''


def _pre_request_notification_flood_script() -> str:
    return f'''
import json
import sys
for index in range({MAX_STDOUT_QUEUE_FRAMES + 1}):
    print(json.dumps({{"jsonrpc": "2.0", "method": "notifications/progress", "params": {{"progress": index}}}}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    print(json.dumps({{"jsonrpc": "2.0", "id": request["id"], "result": {{"ok": True}}}}), flush=True)
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

    def test_notifications_are_allowed_while_waiting_for_response(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _NOTIFICATION_THEN_RESPONSE],
            request_timeout_seconds=1.0,
        )
        try:
            self.assertEqual(client.request("ping"), {"ok": True})
        finally:
            client.close()

    def test_non_json_stdout_fails_closed(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _DIRTY_STDOUT],
            request_timeout_seconds=1.0,
        )
        try:
            with self.assertRaisesRegex(McpError, "stdout contained non-JSON data"):
                client.request("ping")
        finally:
            client.close()

    def test_oversized_stdout_frame_fails_before_json_parsing(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _oversized_stdout_script()],
            request_timeout_seconds=2.0,
        )
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(McpError, "exceeded the maximum allowed JSON-RPC frame size"):
                client.request("ping")
            self.assertLess(time.monotonic() - started, 2.0)
        finally:
            client.close()

    def test_pending_stdout_queue_overflow_fails_closed(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _pre_request_notification_flood_script()],
            request_timeout_seconds=1.0,
        )
        try:
            deadline = time.monotonic() + 1.0
            while not client._stdout_overflow.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(client._stdout_overflow.is_set())
            self.assertLessEqual(client._stdout_queue.qsize(), MAX_STDOUT_QUEUE_FRAMES)
            with self.assertRaisesRegex(McpError, "bounded pending-frame queue capacity"):
                client.request("ping")
        finally:
            client.close()

    def test_unexpected_response_id_fails_closed(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _WRONG_ID],
            request_timeout_seconds=1.0,
        )
        try:
            with self.assertRaisesRegex(McpError, "unexpected response id"):
                client.request("ping")
        finally:
            client.close()

    def test_invalid_jsonrpc_version_fails_closed(self) -> None:
        client = StdioClient(
            [sys.executable, "-u", "-c", _MALFORMED_ENVELOPE],
            request_timeout_seconds=1.0,
        )
        try:
            with self.assertRaisesRegex(McpError, "jsonrpc=2.0"):
                client.request("ping")
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
