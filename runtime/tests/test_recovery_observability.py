import unittest
from types import SimpleNamespace

from recovery_observability import (
    RECOVERY_STATES,
    prometheus_recovery_metrics,
    recovery_observability,
)


def snapshot(status=None, *, accepted=False, samples=()):
    if status is None:
        return SimpleNamespace(outcome=None)
    action = SimpleNamespace(accepted=accepted)
    outcome = SimpleNamespace(status=status, action_result=action, samples=tuple(samples))
    return SimpleNamespace(outcome=outcome)


class RecoveryObservabilityTests(unittest.TestCase):
    def test_no_outcome_is_fixed_none_state(self):
        view = recovery_observability(snapshot(), "approved")
        self.assertEqual("none", view.state)
        self.assertFalse(view.action_accepted)
        self.assertFalse(view.recheck_eligible)
        self.assertFalse(view.verified)
        self.assertEqual(0, view.sample_count)
        self.assertTrue(view.checkpoint_phase_consistent)

    def test_accepted_unverified_is_recheck_eligible_but_not_verified(self):
        view = recovery_observability(
            snapshot("recovery_unverified", accepted=True, samples=(1, 2, 3)),
            "resolved",
        )
        self.assertTrue(view.action_accepted)
        self.assertTrue(view.recheck_eligible)
        self.assertFalse(view.verified)
        self.assertEqual(3, view.sample_count)
        self.assertTrue(view.checkpoint_phase_consistent)

    def test_recovered_is_verified_and_not_recheck_eligible(self):
        view = recovery_observability(
            snapshot("recovered", accepted=True, samples=(1, 2)),
            "resolved",
        )
        self.assertEqual("recovered", view.state)
        self.assertTrue(view.verified)
        self.assertFalse(view.recheck_eligible)

    def test_unverified_without_literal_acceptance_cannot_be_rechecked(self):
        view = recovery_observability(
            snapshot("recovery_unverified", accepted=False, samples=(1,)),
            "resolved",
        )
        self.assertFalse(view.action_accepted)
        self.assertFalse(view.recheck_eligible)

    def test_unknown_status_fails_closed_into_fixed_bucket(self):
        view = recovery_observability(snapshot("provider_custom_state", accepted=True), "resolved")
        self.assertEqual("unknown", view.state)
        self.assertFalse(view.recheck_eligible)
        self.assertFalse(view.verified)

    def test_outcome_requires_resolved_checkpoint_phase(self):
        view = recovery_observability(snapshot("recovered", accepted=True), "dispatching")
        self.assertFalse(view.checkpoint_phase_consistent)

    def test_sample_count_is_bounded_and_tuple_only(self):
        view = recovery_observability(
            snapshot("recovery_unverified", accepted=True, samples=range(150)),
            "resolved",
        )
        self.assertEqual(100, view.sample_count)
        malformed = SimpleNamespace(
            outcome=SimpleNamespace(
                status="recovery_unverified",
                action_result=SimpleNamespace(accepted=True),
                samples=[1, 2, 3],
            )
        )
        self.assertEqual(0, recovery_observability(malformed, "resolved").sample_count)

    def test_prometheus_surface_has_fixed_state_labels_only(self):
        metrics = prometheus_recovery_metrics(
            snapshot("recovery_unverified", accepted=True, samples=(1, 2)),
            "resolved",
        )
        for state in RECOVERY_STATES:
            expected = 1 if state == "recovery_unverified" else 0
            self.assertIn(f'stageguard_recovery_state{{state="{state}"}} {expected}', metrics)
        self.assertIn("stageguard_recovery_recheck_eligible 1", metrics)
        self.assertIn("stageguard_recovery_verified 0", metrics)
        self.assertIn("stageguard_recovery_sample_count 2", metrics)
        self.assertIn("stageguard_recovery_checkpoint_phase_consistent 1", metrics)
        for forbidden in (
            "incident-",
            "revision",
            "datasource",
            "query=",
            "operator@",
            "operation_id",
            "target=",
        ):
            self.assertNotIn(forbidden, metrics)


if __name__ == "__main__":
    unittest.main()
