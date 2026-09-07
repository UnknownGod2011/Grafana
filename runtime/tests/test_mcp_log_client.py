#!/usr/bin/env python3
import json
import unittest

from mcp_log_client import McpLogError, extract_log_query_result


def result(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class McpLogClientTests(unittest.TestCase):
    def test_parses_full_log_payload_and_metadata(self):
        parsed = extract_log_query_result(
            result({
                "data": [{
                    "timestamp": "1760000000000000000",
                    "line": '{"event":"packet_loss_alarm"}',
                    "labels": {"production_id": "broadcast-alpha", "uplink": "uplink-b"},
                    "structuredMetadata": {"source": "switch"},
                    "parsed": {"event": "packet_loss_alarm"},
                }],
                "metadata": {
                    "linesReturned": 1,
                    "resultsTruncated": False,
                    "startTime": "2026-09-07T00:00:00Z",
                    "endTime": "2026-09-07T00:05:00Z",
                },
            }),
            requested_limit=8,
            requested_start="now-5m",
            requested_end="now",
        )
        self.assertEqual(1, len(parsed.records))
        self.assertFalse(parsed.truncated)
        self.assertEqual("packet_loss_alarm", parsed.records[0].parsed["event"])

    def test_legacy_payload_at_exact_limit_is_treated_as_truncated(self):
        data = [
            {"timestamp": str(i), "line": "x", "labels": {}, "parsed": {}, "structuredMetadata": {}}
            for i in range(2)
        ]
        parsed = extract_log_query_result(
            result({"data": data}),
            requested_limit=2,
            requested_start="now-5m",
            requested_end="now",
        )
        self.assertTrue(parsed.truncated)

    def test_metadata_count_mismatch_fails_closed(self):
        with self.assertRaises(McpLogError):
            extract_log_query_result(
                result({
                    "data": [{"timestamp": "1", "line": "x", "labels": {}}],
                    "metadata": {"linesReturned": 2, "resultsTruncated": False},
                }),
                requested_limit=8,
                requested_start="now-5m",
                requested_end="now",
            )

    def test_non_string_label_value_fails_closed(self):
        with self.assertRaises(McpLogError):
            extract_log_query_result(
                result({"data": [{"timestamp": "1", "line": "x", "labels": {"pod": 3}}]}),
                requested_limit=8,
                requested_start="now-5m",
                requested_end="now",
            )

    def test_more_than_requested_limit_fails_closed(self):
        data = [{"timestamp": str(i), "line": "x", "labels": {}} for i in range(3)]
        with self.assertRaises(McpLogError):
            extract_log_query_result(
                result({"data": data}),
                requested_limit=2,
                requested_start="now-5m",
                requested_end="now",
            )


if __name__ == "__main__":
    unittest.main()
