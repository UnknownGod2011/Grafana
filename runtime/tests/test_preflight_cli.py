import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import preflight


class PreflightCliTests(unittest.TestCase):
    def test_failure_payload_never_serializes_exception_message(self):
        secret = "https://operator:super-secret@example.invalid/api?token=abc123"
        payload = preflight._failure_payload(RuntimeError(f"provider failed at {secret}"))

        serialized = json.dumps(payload, sort_keys=True)
        self.assertEqual(False, payload["ready"])
        self.assertEqual("preflight failed", payload["error"])
        self.assertEqual("RuntimeError", payload["error_type"])
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("abc123", serialized)
        self.assertNotIn("example.invalid", serialized)

    def test_main_redacts_secret_bearing_startup_failure(self):
        secret = "Bearer top-secret-token"
        output = io.StringIO()

        with patch.object(sys, "argv", ["preflight.py", "telemetry.json"]), patch.object(
            preflight,
            "load_telemetry_profile",
            side_effect=ValueError(f"invalid datasource configuration: {secret}"),
        ), redirect_stdout(output):
            status = preflight.main()

        self.assertEqual(2, status)
        payload = json.loads(output.getvalue())
        self.assertEqual(
            {"ready": False, "error": "preflight failed", "error_type": "ValueError"},
            payload,
        )
        self.assertNotIn("top-secret-token", output.getvalue())


if __name__ == "__main__":
    unittest.main()
