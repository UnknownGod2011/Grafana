import unittest

from durable_audit_reader import GoogleCloudAuditReader


NOW_MS = 1_700_000_000_000


class FakeLogger:
    full_name = "projects/test-project/logs/stageguard-audit"

    def __init__(self):
        self.calls = []

    def list_entries(self, **kwargs):
        self.calls.append(kwargs)
        return []


class AuditFilterSecurityTests(unittest.TestCase):
    def test_quotes_and_backslashes_remain_inside_incident_literal(self):
        logger = FakeLogger()
        reader = GoogleCloudAuditReader(logger, clock_ms=lambda: NOW_MS)
        reader.read(incident_id='incident\\" OR severity>=ERROR')
        filter_ = logger.calls[0]["filter_"]
        self.assertIn('jsonPayload.incident_id="incident\\\\\\\" OR severity>=ERROR"', filter_)
        self.assertEqual(1, filter_.count("jsonPayload.incident_id="))

    def test_control_characters_are_rejected_before_logging_query(self):
        for control in ("\n", "\r", "\t", "\x00", "\x1f", "\x7f"):
            with self.subTest(control=repr(control)):
                logger = FakeLogger()
                reader = GoogleCloudAuditReader(logger, clock_ms=lambda: NOW_MS)
                with self.assertRaisesRegex(ValueError, "control characters"):
                    reader.read(incident_id=f"incident{control}OR true")
                self.assertEqual([], logger.calls)

    def test_control_characters_in_logger_name_fail_during_construction(self):
        for control in ("\n", "\t", "\x00", "\x7f"):
            with self.subTest(control=repr(control)):
                logger = FakeLogger()
                logger.full_name = f"projects/test/logs/stageguard{control}OR true"
                with self.assertRaisesRegex(ValueError, "control characters"):
                    GoogleCloudAuditReader(logger, clock_ms=lambda: NOW_MS)


if __name__ == "__main__":
    unittest.main()
