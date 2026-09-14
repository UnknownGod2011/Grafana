import unittest

from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class CountingRemediation:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(self.accepted, "provider detail must not control lifecycle")


def diagnosed_prefix():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def unhealthy_recovery_window():
    return [8.0, 5.0] * 6


def healthy_recovery_streak():
    return [0.2, 0.2, 0.1, 0.1]


class RecoveryRecheckTests(unittest.TestCase):
    def make_service(self, values, *, accepted=True):
        metrics = SequenceMetrics(values)
        remediation = CountingRemediation(accepted=accepted)
        audit = MemoryAuditLog()
        service = IncidentService(
            metrics,
            remediation,
            audit,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        return service, remediation, audit

    def approve_current(self, service):
        snapshot = service.investigate()
        return service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )

    def test_recheck_proves_recovery_without_replaying_provider(self):
        values = diagnosed_prefix() + unhealthy_recovery_window() + healthy_recovery_streak()
        service, remediation, audit = self.make_service(values)
        self.approve_current(service)

        first = service.execute_approved()
        self.assertEqual("recovery_unverified", first.outcome.status)
        self.assertEqual(1, len(remediation.calls))

        final = service.recheck_recovery(actor="operator@example.com")
        self.assertEqual("recovered", final.outcome.status)
        self.assertEqual(1, len(remediation.calls), "recovery recheck must never dispatch remediation")
        self.assertEqual(2, len(final.outcome.samples))
        self.assertEqual("recovery_rechecked", audit.events[-1].event_type)
        self.assertEqual(False, audit.events[-1].payload["provider_replayed"])
        self.assertEqual("recovered", audit.events[-1].payload["status"])

    def test_recheck_can_remain_unverified_without_replaying_provider(self):
        values = diagnosed_prefix() + unhealthy_recovery_window() + unhealthy_recovery_window()
        service, remediation, audit = self.make_service(values)
        self.approve_current(service)
        service.execute_approved()

        result = service.recheck_recovery()
        self.assertEqual("recovery_unverified", result.outcome.status)
        self.assertEqual(1, len(remediation.calls))
        self.assertEqual("recovery_rechecked", audit.events[-1].event_type)
        self.assertEqual(6, audit.events[-1].payload["sample_count"])

    def test_recheck_is_rejected_before_any_completed_action(self):
        service, remediation, _ = self.make_service(diagnosed_prefix())
        with self.assertRaises(RuntimeError):
            service.recheck_recovery()
        self.assertEqual([], remediation.calls)

    def test_recheck_is_rejected_after_action_failure(self):
        service, remediation, _ = self.make_service(diagnosed_prefix(), accepted=False)
        self.approve_current(service)
        result = service.execute_approved()
        self.assertEqual("action_failed", result.outcome.status)

        with self.assertRaises(RuntimeError):
            service.recheck_recovery()
        self.assertEqual(1, len(remediation.calls))

    def test_recheck_is_rejected_after_recovery_is_already_proven(self):
        values = diagnosed_prefix() + healthy_recovery_streak()
        service, remediation, _ = self.make_service(values)
        self.approve_current(service)
        result = service.execute_approved()
        self.assertEqual("recovered", result.outcome.status)

        with self.assertRaises(RuntimeError):
            service.recheck_recovery()
        self.assertEqual(1, len(remediation.calls))


if __name__ == "__main__":
    unittest.main()
