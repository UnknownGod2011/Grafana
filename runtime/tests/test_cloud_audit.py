import math
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

    def test_allows_existing_bounded_remediation_metadata_shape(self):
        document = audit_event_document(
            self.event(
                {
                    "revision": "abc123",
                    "status": "recovered",
                    "action_metadata": {
                        "adapter": "allowlisted_production",
                        "operation_id": "sg-0123456789012345678901234567890123456789",
                        "attempt_count": 1,
                        "transport_status": 202,
                    },
                }
            )
        )
        self.assertEqual("allowlisted_production", document["payload"]["action_metadata"]["adapter"])

    def test_rejects_sensitive_or_query_shaped_payload_keys_at_any_supported_depth(self):
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
                with self.assertRaises(ValueError):
                    audit_event_document(self.event({"action_metadata": {key: "must-not-be-written"}}))

    def test_rejects_collections_deep_nesting_and_oversized_values(self):
        payloads = (
            {"items": [1, 2]},
            {"nested": {"items": [1]}},
            {"nested": {"too_deep": {"x": 1}}},
            {"value": "x" * 2049},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    audit_event_document(self.event(payload))

    def test_rejects_non_finite_payload_numbers_at_any_supported_depth(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    audit_event_document(self.event({"confidence": value}))
                with self.assertRaises(ValueError):
                    audit_event_document(self.event({"action_metadata": {"duration_seconds": value}}))

    def test_rejects_boolean_or_non_integer_sequence_and_timestamp(self):
        invalid_envelopes = (
            AuditEvent(True, 1_700_000_000_000, "incident", "event", "actor", {}),
            AuditEvent(7.0, 1_700_000_000_000, "incident", "event", "actor", {}),
            AuditEvent(7, False, "incident", "event", "actor", {}),
            AuditEvent(7, 1_700_000_000_000.0, "incident", "event", "actor", {}),
        )
        for event in invalid_envelopes:
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    audit_event_document(event)

    def test_rejects_non_string_envelope_fields_through_value_error_boundary(self):
        invalid_envelopes = (
            AuditEvent(7, 1_700_000_000_000, 123, "event", "actor", {}),
            AuditEvent(7, 1_700_000_000_000, "incident", b"event", "actor", {}),
            AuditEvent(7, 1_700_000_000_000, "incident", "event", None, {}),
        )
        for event in invalid_envelopes:
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    audit_event_document(event)

    def test_rejects_ascii_control_characters_in_envelope_fields(self):
        invalid_envelopes = (
            AuditEvent(7, 1_700_000_000_000, "incident\nforged", "event", "actor", {}),
            AuditEvent(7, 1_700_000_000_000, "incident", "event\x00type", "actor", {}),
            AuditEvent(7, 1_700_000_000_000, "incident", "event", "actor\x1bspoof", {}),
        )
        for event in invalid_envelopes:
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    audit_event_document(event)

    def test_envelope_size_limits_are_measured_in_utf8_bytes(self):
        accepted = AuditEvent(7, 1_700_000_000_000, "é" * 128, "e" * 128, "a" * 512, {})
        document = audit_event_document(accepted)
        self.assertEqual("é" * 128, document["incident_id"])

        rejected = (
            AuditEvent(7, 1_700_000_000_000, "é" * 129, "event", "actor", {}),
            AuditEvent(7, 1_700_000_000_000, "incident", "é" * 65, "actor", {}),
            AuditEvent(7, 1_700_000_000_000, "incident", "event", "é" * 257, {}),
        )
        for event in rejected:
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    audit_event_document(event)

    def test_rejects_non_mapping_payload(self):
        with self.assertRaises(ValueError):
            audit_event_document(AuditEvent(7, 1_700_000_000_000, "incident", "event", "actor", []))

    def test_accepts_finite_payload_numbers_and_integer_envelope(self):
        document = audit_event_document(self.event({"confidence": 0.0, "attempt_count": 1}))
        self.assertEqual(0.0, document["payload"]["confidence"])
        self.assertEqual(1, document["payload"]["attempt_count"])

    def test_rejects_invalid_event_envelope(self):
        bad = AuditEvent(0, 1, "incident", "event", "actor", {})
        with self.assertRaises(ValueError):
            audit_event_document(bad)


if __name__ == "__main__":
    unittest.main()
