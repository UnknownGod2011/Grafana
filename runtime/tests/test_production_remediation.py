import unittest

from investigator import IncidentReport
from production_remediation import (
    AllowlistedProductionRemediationClient,
    TransportResult,
)
from remediation import Approval, remediate_and_verify, remediation_operation_id


class SequenceTransport:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []
        self.timeouts = []

    def execute(self, request, *, timeout_seconds):
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)

    def instant(self, _query):
        return self.values.pop(0)


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


class ProductionRemediationTests(unittest.TestCase):
    def test_operation_identity_is_deterministic_and_not_actor_bound(self):
        report = diagnosed_report()
        first = remediation_operation_id(report, approval())
        second = remediation_operation_id(
            report,
            Approval(True, "second@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sg-"))
        self.assertEqual(43, len(first))

    def test_adapter_refuses_non_allowlisted_target_without_transport_call(self):
        transport = SequenceTransport([])
        client = AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="prod-1",
            allowed_uplink="uplink-safe",
        )
        result = client.recover_uplink_idempotent("prod-1", "other", "sg-" + "a" * 40)
        self.assertFalse(result.accepted)
        self.assertEqual([], transport.requests)

    def test_retry_reuses_identical_operation_identity(self):
        transport = SequenceTransport([
            TransportResult(False, 503, retryable=True),
            TransportResult(True, 202, retryable=False),
        ])
        client = AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="broadcast-alpha",
            allowed_uplink="uplink-b",
            retry_delay_seconds=0,
            sleep=lambda _: None,
        )
        outcome = remediate_and_verify(
            diagnosed_report(), approval(), client,
            SequenceMetrics([0.1, 0.1, 0.1, 0.1]),
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovered", outcome.status)
        self.assertEqual(2, len(transport.requests))
        self.assertEqual(transport.requests[0], transport.requests[1])
        self.assertEqual("recover_uplink", transport.requests[0].action)
        self.assertEqual("broadcast-alpha", transport.requests[0].production_id)
        self.assertEqual("uplink-b", transport.requests[0].target)
        self.assertEqual(2, outcome.action_result.metadata["attempt_count"])
        self.assertEqual(202, outcome.action_result.metadata["transport_status"])

    def test_non_retryable_failure_does_not_retry_or_check_recovery(self):
        transport = SequenceTransport([TransportResult(False, 403, retryable=False)])
        client = AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="broadcast-alpha",
            allowed_uplink="uplink-b",
            sleep=lambda _: None,
        )
        metrics = SequenceMetrics([])
        outcome = remediate_and_verify(diagnosed_report(), approval(), client, metrics, sleep=lambda _: None)
        self.assertEqual("action_failed", outcome.status)
        self.assertEqual(1, len(transport.requests))
        self.assertEqual([], metrics.values)

    def test_transport_timeout_is_bounded_and_retryable(self):
        transport = SequenceTransport([TimeoutError(), TransportResult(False, 503, retryable=True)])
        client = AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="broadcast-alpha",
            allowed_uplink="uplink-b",
            timeout_seconds=1.5,
            max_attempts=2,
            retry_delay_seconds=0,
            sleep=lambda _: None,
        )
        result = client.recover_uplink_idempotent("broadcast-alpha", "uplink-b", "sg-" + "b" * 40)
        self.assertFalse(result.accepted)
        self.assertEqual([1.5, 1.5], transport.timeouts)
        self.assertEqual(2, result.metadata["attempt_count"])

    def test_construction_rejects_unbounded_policy(self):
        transport = SequenceTransport([])
        with self.assertRaises(ValueError):
            AllowlistedProductionRemediationClient(
                transport,
                allowed_production_id="broadcast-alpha",
                allowed_uplink="uplink-b",
                timeout_seconds=30,
            )
        with self.assertRaises(ValueError):
            AllowlistedProductionRemediationClient(
                transport,
                allowed_production_id="broadcast-alpha",
                allowed_uplink="uplink-b",
                max_attempts=10,
            )


if __name__ == "__main__":
    unittest.main()
