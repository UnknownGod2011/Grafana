from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from mcp_fixture_replay import FixtureReplayError, MAX_EXPECTED_LABELS, MAX_FIXTURE_BYTES, load_fixture, validate_fixture


def _fixture():
    labels = {"production_id": "broadcast-alpha", "uplink": "uplink-b"}
    return {
        "tools_list": {
            "tools": [
                {"name": "list_datasources", "annotations": {"readOnlyHint": True}},
                {"name": "query_prometheus", "annotations": {"readOnlyHint": True}},
            ]
        },
        "list_datasources": {"content": [{"type": "text", "text": '{"uid":"stageguard-prometheus"}'}]},
        "query_prometheus": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"data": {"resultType": "vector", "result": [{"metric": labels, "value": [1780000000.0, "3.25"]}]}}),
                }
            ]
        },
        "datasource_uid": "stageguard-prometheus",
        "expected_labels": labels,
    }


class FixtureReplayTests(unittest.TestCase):
    def test_valid_capture_replays_through_production_boundaries(self):
        report = validate_fixture(_fixture())
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["datasource_uid"], "stageguard-prometheus")
        self.assertEqual(report["tool_count"], 2)
        self.assertEqual(report["matched_labels"]["uplink"], "uplink-b")

    def test_write_capable_tool_fails_closed(self):
        fixture = _fixture()
        fixture["tools_list"]["tools"].append({"name": "delete_datasource", "annotations": {"readOnlyHint": False}})
        with self.assertRaises(FixtureReplayError):
            validate_fixture(fixture)

    def test_wrong_datasource_fails_closed(self):
        fixture = _fixture()
        fixture["datasource_uid"] = "different"
        with self.assertRaises(FixtureReplayError):
            validate_fixture(fixture)

    def test_wrong_series_labels_fail_closed(self):
        fixture = _fixture()
        fixture["expected_labels"]["uplink"] = "uplink-a"
        with self.assertRaises(FixtureReplayError):
            validate_fixture(fixture)

    def test_expected_labels_cardinality_is_bounded_before_evidence_walk(self):
        fixture = _fixture()
        fixture["expected_labels"] = {f"label_{index}": "x" for index in range(MAX_EXPECTED_LABELS + 1)}
        with self.assertRaises(FixtureReplayError):
            validate_fixture(fixture)

    def test_invalid_prometheus_label_name_fails_closed(self):
        fixture = _fixture()
        fixture["expected_labels"] = {"not-a-label": "x"}
        with self.assertRaises(FixtureReplayError):
            validate_fixture(fixture)

    def test_label_limits_are_utf8_byte_oriented(self):
        fixture = _fixture()
        fixture["expected_labels"] = {"uplink": "é" * 300}
        with self.assertRaises(FixtureReplayError):
            validate_fixture(fixture)

    def test_loader_rejects_duplicate_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text('{"tools_list":{},"tools_list":{},"list_datasources":{},"query_prometheus":{},"datasource_uid":"x","expected_labels":{}}', encoding="utf-8")
            with self.assertRaises(FixtureReplayError):
                load_fixture(path)

    def test_loader_rejects_extra_fields(self):
        fixture = _fixture()
        fixture["secret"] = "must-not-be-captured"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaises(FixtureReplayError):
                load_fixture(path)

    def test_loader_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_bytes(b"")
            with self.assertRaises(FixtureReplayError):
                load_fixture(path)

    def test_loader_rejects_oversized_file_from_bytes_actually_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_bytes(b" " * (MAX_FIXTURE_BYTES + 1))
            with self.assertRaises(FixtureReplayError):
                load_fixture(path)

    def test_loader_rejects_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_bytes(b"\xff")
            with self.assertRaises(FixtureReplayError):
                load_fixture(path)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes are not available on this platform")
    def test_loader_rejects_fifo_without_attempting_to_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.pipe"
            os.mkfifo(path)
            # Open the FIFO read/write so load_fixture's open succeeds immediately.
            # The production fstat check must reject it before calling read().
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
            try:
                with self.assertRaisesRegex(FixtureReplayError, "regular file"):
                    load_fixture(path)
            finally:
                os.close(fd)


if __name__ == "__main__":
    unittest.main()
