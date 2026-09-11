import unittest

from investigator import IncidentReport
from remediation import ActionResult, Approval, remediate_and_verify


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class FakeRemediation:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(self.accepted, "ok" if self.accepted else "rejected")


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


def unavailable_report():
    return IncidentReport(
        status="abstain",
        production_id="broadcast-alpha",
        affected_feed="cam-3",
        hypothesis=None,
        confidence=0.0,
        summary="Required incident evidence is temporarily unavailable; no diagnosis or remediation is permitted.",
        missing_evidence=(),
        evidence=(),
        unavailable_evidence=("causal",),
    )


class RemediationTests(unittest.TestCase):
    def test_no_action_without_explicit_matching_approval(self):
        action = FakeRemediation()
        outcome = remediate_and_verify(
            diagnosed_report(),
            Approval(False, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
            action,
            SequenceMetrics([]),
            sleep=lambda _: None,
        )
        self.assertEqual("approval_required", outcome.status)
        self.assertEqual([], action.calls)

    def test_mismatched_target_cannot_execute(self):
        action = FakeRemediation()
        outcome = remediate_and_verify(
            diagnosed_report(),
            Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-a"),
            action,
            SequenceMetrics([]),
            sleep=lambda _: None,
        )
        self.assertEqual("approval_required", outcome.status)
        self.assertEqual([], action.calls)

    def test_evidence_unavailable_abstention_cannot_execute_even_with_matching_approval(self):
        action = FakeRemediation()
        outcome = remediate_and_verify(
            unavailable_report(),
            Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
            action,
            SequenceMetrics([]),
            sleep=lambda _: None,
        )
        self.assertEqual("approval_required", outcome.status)
        self.assertEqual([], action.calls)

    def test_action_success_is_not_recovery(self):
        action = FakeRemediation()
        metrics = SequenceMetrics([0.3, 4.0, 0.3, 3.0, 0.3, 2.0])
        outcome = remediate_and_verify(
            diagnosed_report(),
            Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
            action,
            metrics,
            max_attempts=3,
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovery_unverified", outcome.status)
        self.assertTrue(outcome.action_result.accepted)
        self.assertEqual(3, len(outcome.samples))

    def test_requires_consecutive_healthy_samples(self):
        action = FakeRemediation()
        metrics = SequenceMetrics([
            0.3, 0.5,
            0.3, 1.5,
            0.3, 0.4,
            0.3, 0.2,
        ])
        outcome = remediate_and_verify(
            diagnosed_report(),
            Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
            action,
            metrics,
            max_attempts=4,
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovered", outcome.status)
        self.assertEqual(4, len(outcome.samples))

    def test_missing_telemetry_resets_health_streak(self):
        action = FakeRemediation()
        metrics = SequenceMetrics([
            0.3, 0.4,
            None, 0.2,
            0.3, 0.3,
        ])
        outcome = remediate_and_verify(
            diagnosed_report(),
            Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
            action,
            metrics,
            max_attempts=3,
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovery_unverified", outcome.status)

    def test_rejected_action_does_not_query_recovery_metrics(self):
        action = FakeRemediation(accepted=False)
        metrics = SequenceMetrics([])
        outcome = remediate_and_verify(
            diagnosed_report(),
            Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b"),
            action,
            metrics,
            sleep=lambda _: None,
        )
        self.assertEqual("action_failed", outcome.status)
        self.assertEqual(1, len(action.calls))


if __name__ == "__main__":
    unittest.main()
