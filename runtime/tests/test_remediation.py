import math
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
    def _approved(self):
        return Approval(True, "operator@example.com", "recover_uplink", "broadcast-alpha", "uplink-b")

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
            self._approved(),
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
            self._approved(),
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
            self._approved(),
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
            self._approved(),
            action,
            metrics,
            max_attempts=3,
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovery_unverified", outcome.status)

    def test_boolean_false_samples_cannot_false_positive_recovery(self):
        action = FakeRemediation()
        outcome = remediate_and_verify(
            diagnosed_report(),
            self._approved(),
            action,
            SequenceMetrics([False, False, False, False]),
            max_attempts=2,
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovery_unverified", outcome.status)
        self.assertEqual(2, len(outcome.samples))
        self.assertTrue(all(sample.packet_loss_percent is None for sample in outcome.samples))
        self.assertTrue(all(sample.dropped_frames_per_second is None for sample in outcome.samples))
        self.assertTrue(all(not sample.healthy for sample in outcome.samples))

    def test_boolean_true_samples_are_unavailable_not_numeric(self):
        outcome = remediate_and_verify(
            diagnosed_report(),
            self._approved(),
            FakeRemediation(),
            SequenceMetrics([True, True]),
            max_attempts=1,
            required_consecutive_healthy=1,
            sleep=lambda _: None,
        )
        self.assertEqual("recovery_unverified", outcome.status)
        self.assertIsNone(outcome.samples[0].packet_loss_percent)
        self.assertIsNone(outcome.samples[0].dropped_frames_per_second)

    def test_non_finite_samples_cannot_prove_recovery(self):
        for invalid in (math.nan, math.inf, -math.inf):
            with self.subTest(invalid=invalid):
                outcome = remediate_and_verify(
                    diagnosed_report(),
                    self._approved(),
                    FakeRemediation(),
                    SequenceMetrics([invalid, invalid]),
                    max_attempts=1,
                    required_consecutive_healthy=1,
                    sleep=lambda _: None,
                )
                self.assertEqual("recovery_unverified", outcome.status)
                self.assertIsNone(outcome.samples[0].packet_loss_percent)
                self.assertIsNone(outcome.samples[0].dropped_frames_per_second)
                self.assertFalse(outcome.samples[0].healthy)

    def test_numeric_strings_and_objects_cannot_prove_recovery(self):
        for invalid in ("0", "0.0", object()):
            with self.subTest(type=type(invalid).__name__):
                outcome = remediate_and_verify(
                    diagnosed_report(),
                    self._approved(),
                    FakeRemediation(),
                    SequenceMetrics([invalid, invalid]),
                    max_attempts=1,
                    required_consecutive_healthy=1,
                    sleep=lambda _: None,
                )
                self.assertEqual("recovery_unverified", outcome.status)
                self.assertIsNone(outcome.samples[0].packet_loss_percent)
                self.assertIsNone(outcome.samples[0].dropped_frames_per_second)

    def test_finite_integer_samples_are_normalized_and_can_verify_recovery(self):
        outcome = remediate_and_verify(
            diagnosed_report(),
            self._approved(),
            FakeRemediation(),
            SequenceMetrics([0, 0]),
            max_attempts=1,
            required_consecutive_healthy=1,
            sleep=lambda _: None,
        )
        self.assertEqual("recovered", outcome.status)
        self.assertEqual(0.0, outcome.samples[0].packet_loss_percent)
        self.assertEqual(0.0, outcome.samples[0].dropped_frames_per_second)
        self.assertTrue(outcome.samples[0].healthy)

    def test_one_malformed_metric_resets_health_streak(self):
        outcome = remediate_and_verify(
            diagnosed_report(),
            self._approved(),
            FakeRemediation(),
            SequenceMetrics([
                0.3, 0.4,
                False, 0.2,
                0.3, 0.3,
            ]),
            max_attempts=3,
            required_consecutive_healthy=2,
            sleep=lambda _: None,
        )
        self.assertEqual("recovery_unverified", outcome.status)
        self.assertTrue(outcome.samples[0].healthy)
        self.assertFalse(outcome.samples[1].healthy)
        self.assertTrue(outcome.samples[2].healthy)

    def test_rejected_action_does_not_query_recovery_metrics(self):
        action = FakeRemediation(accepted=False)
        metrics = SequenceMetrics([])
        outcome = remediate_and_verify(
            diagnosed_report(),
            self._approved(),
            action,
            metrics,
            sleep=lambda _: None,
        )
        self.assertEqual("action_failed", outcome.status)
        self.assertEqual(1, len(action.calls))


if __name__ == "__main__":
    unittest.main()
