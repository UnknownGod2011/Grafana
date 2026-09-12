import json
import unittest

from incident_service import IncidentService, MemoryAuditLog
from investigator import IncidentReport
from remediation import ActionResult, Approval, remediate_and_verify


SECRET = "https://provider.internal/control?token=super-secret-bearer"


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)

    def instant(self, _query):
        if not self.values:
            raise AssertionError("unexpected metric query")
        return self.values.pop(0)


class SecretBearingRemediation:
    def __init__(self, accepted=True):
        self.accepted = accepted

    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(
            self.accepted,
            f"provider response contained {SECRET}",
            {
                "token": SECRET,
                "provider_body": {"authorization": SECRET},
                "adapter": "custom-secret-bearing-adapter",
            },
        )


class ProductionMetadataRemediation:
    def recover_uplink_idempotent(self, _production_id, _uplink, operation_id):
        return ActionResult(
            True,
            f"provider body must not survive: {SECRET}",
            {
                "adapter": "allowlisted_production",
                "operation_id": operation_id,
                "attempt_count": 2,
                "transport_status": 202,
                "provider_secret": SECRET,
            },
        )


def diagnosed_report():
    return IncidentReport(
        status="diagnosed",
        production_id="broadcast-alpha",
        affected_feed="cam-3",
        hypothesis="uplink-b packet loss",
        confidence=0.97,
        summary="diagnosed",
        missing_evidence=(),
        evidence=(),
    )


def approval():
    return Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b")


def diagnosed_then_recovered_metrics():
    return SequenceMetrics([
        4.0, 18.0, 41.0, 37.0, 0.2, 0.1,
        0.2, 0.2,
        0.1, 0.1,
    ])


class RemediationResultBoundaryTests(unittest.TestCase):
    def test_custom_adapter_detail_and_metadata_are_discarded_before_outcome(self):
        outcome = remediate_and_verify(
            diagnosed_report(),
            approval(),
            SecretBearingRemediation(),
            SequenceMetrics([0.1, 0.1, 0.1, 0.1]),
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )

        self.assertEqual("recovered", outcome.status)
        self.assertIsNotNone(outcome.action_result)
        self.assertEqual("remediation action accepted", outcome.action_result.detail)
        self.assertEqual({}, outcome.action_result.metadata)
        serialized = json.dumps(outcome.to_dict(), sort_keys=True)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("provider_body", serialized)
        self.assertNotIn("authorization", serialized)

    def test_rejected_custom_adapter_detail_is_also_redacted(self):
        outcome = remediate_and_verify(
            diagnosed_report(),
            approval(),
            SecretBearingRemediation(accepted=False),
            SequenceMetrics([]),
            sleep=lambda _: None,
        )

        self.assertEqual("action_failed", outcome.status)
        self.assertEqual("remediation action rejected or failed", outcome.action_result.detail)
        self.assertEqual({}, outcome.action_result.metadata)
        self.assertNotIn(SECRET, json.dumps(outcome.to_dict(), sort_keys=True))

    def test_stageguard_production_operation_metadata_survives_without_extra_provider_fields(self):
        outcome = remediate_and_verify(
            diagnosed_report(),
            approval(),
            ProductionMetadataRemediation(),
            SequenceMetrics([0.1, 0.1, 0.1, 0.1]),
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )

        metadata = outcome.action_result.metadata
        self.assertEqual("allowlisted_production", metadata["adapter"])
        self.assertTrue(metadata["operation_id"].startswith("sg-"))
        self.assertEqual(2, metadata["attempt_count"])
        self.assertEqual(202, metadata["transport_status"])
        self.assertNotIn("provider_secret", metadata)
        self.assertNotIn(SECRET, json.dumps(outcome.to_dict(), sort_keys=True))

    def test_incident_audit_never_receives_custom_provider_detail_or_metadata(self):
        audit = MemoryAuditLog()
        service = IncidentService(
            diagnosed_then_recovered_metrics(),
            SecretBearingRemediation(),
            audit,
            clock_ms=lambda: 123,
            id_factory=lambda: "incident-result-boundary",
            recovery_sleep=lambda _: None,
        )
        snapshot = service.investigate()
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        final = service.execute_approved()

        self.assertEqual("recovered", final.outcome.status)
        serialized_snapshot = json.dumps(final.to_dict(), sort_keys=True)
        serialized_audit = json.dumps([event.payload for event in audit.events], sort_keys=True)
        self.assertNotIn(SECRET, serialized_snapshot)
        self.assertNotIn(SECRET, serialized_audit)
        self.assertNotIn("provider_body", serialized_audit)


if __name__ == "__main__":
    unittest.main()
