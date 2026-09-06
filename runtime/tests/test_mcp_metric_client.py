import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_metric_client import McpMetricError, extract_instant_value


def tool_result(payload):
    import json

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload),
            }
        ]
    }


class McpMetricResultTests(unittest.TestCase):
    def test_extracts_single_prometheus_vector_sample(self):
        result = tool_result(
            {
                "data": [
                    {
                        "metric": {
                            "production_id": "broadcast-alpha",
                            "uplink": "uplink-b",
                        },
                        "value": [1788700000.0, "18"],
                    }
                ]
            }
        )
        self.assertEqual(18.0, extract_instant_value(result))

    def test_extracts_prometheus_scalar(self):
        result = tool_result({"data": [1788700000.0, "8.5"]})
        self.assertEqual(8.5, extract_instant_value(result))

    def test_empty_vector_maps_to_missing_evidence(self):
        self.assertIsNone(extract_instant_value(tool_result({"data": []})))

    def test_structured_content_is_accepted(self):
        result = {
            "structuredContent": {
                "data": [
                    {
                        "metric": {},
                        "value": [1788700000.0, "41"],
                    }
                ]
            }
        }
        self.assertEqual(41.0, extract_instant_value(result))

    def test_multiple_series_are_rejected_instead_of_guessed(self):
        result = tool_result(
            {
                "data": [
                    {"metric": {"feed_id": "cam-1"}, "value": [1788700000.0, "0"]},
                    {"metric": {"feed_id": "cam-2"}, "value": [1788700000.0, "0"]},
                ]
            }
        )
        with self.assertRaisesRegex(McpMetricError, "expected exactly one"):
            extract_instant_value(result)

    def test_tool_error_is_not_treated_as_missing_telemetry(self):
        with self.assertRaises(McpMetricError):
            extract_instant_value(
                {
                    "isError": True,
                    "content": [{"type": "text", "text": "permission denied"}],
                }
            )

    def test_malformed_numeric_value_fails_closed(self):
        result = tool_result(
            {
                "data": [
                    {
                        "metric": {},
                        "value": [1788700000.0, "not-a-number"],
                    }
                ]
            }
        )
        with self.assertRaisesRegex(McpMetricError, "not numeric"):
            extract_instant_value(result)


if __name__ == "__main__":
    unittest.main()
