import unittest

from cloud_audit import GoogleCloudLoggingAuditSink, audit_event_document
from incident_service import AuditEvent


class FakeLogger:
    def __init__(self):
        self.calls = []

    def log_struct(self, info, *, severity="NOTICE"):
        self.calls.append((info, severity))


class CloudAuditTests(unittest.TestCase):
    def event(self, payload=None):
        return AuditEvent(
            sequence=7,
            timestamp_unix_ms=1_700_000_000_000,
            incident_id="incident-1",
            event_type="investigation_completed",
            actor="stable-iap-subject",
            payload=payload or {"revision": "abc123", "status": "diagnosed", "confidence": 0.97},
        )

    def test_writes_one_structured_notice_entry(self):
        logger = FakeLogger()
        sink = GoogleCloudLoggingAuditSink(logger)
        sink.append(self.event())

        self.assertEqual(1, len(logger.calls))
        document, severity = logger.calls[0]
        self.assertEqual("NOTICE", severity)
        self.assertEqual("stageguard.audit.v1", document["schema"])
        self.assertEqual("stable-iap-subject", document["actor"])
        self.assertEqual("abc123", document["payload"]["revision"])

    def test_document_is_deterministic_and_contains_no_freeform_message(self):
        document = audit_event_document(self.event())
        self.assertEqual(
            {"schema", "sequence", "timestamp_unix_ms", "incident_id", "event_type", "actor", "payload"},
            set(document),
        )
        self.assertNotIn("message", document)
        self.assertNotIn("text", document)

    def test_rejects_sensitive_or_query_shaped_payload_keys(self):
        blocked = (
            "authorization",
            "api_token",
            "credential_hint",
            "password",
            "client_secret",
            "promql",
            "logql",
            "raw_log_body",
            "prompt",
            "remediation_endpoint",
        )
        for key in blocked:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    audit_event_document(self.event({key: "must-not-be-written"}))

    def test_rejects_nested_payloads_and_oversized_values(self):
        for payload in ({"nested": {"x": 1}}, {"items": [1, 2]}, {"value": "x" * 2049}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    audit_event_document(self.event(payload))

    def test_rejects_invalid_event_envelope(self):
        bad = AuditEvent(0, 1, "incident", "event", "actor", {})
        with self.assertRaises(ValueError):
            audit_event_document(bad)


if __name__ == "__main__":
    unittest.main()
