from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from incident_checkpoint import JsonCheckpointStore
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
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


class MutableClock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class ExecutionWatchdogClockBoundaryTests(unittest.TestCase):
    def service(self, root: Path, clock: MutableClock, remediation: CountingRemediation):
        return AnchoredExecutionSafeIncidentService(
            SequenceMetrics(diagnosed()),
            remediation,
            AnchoredJsonlAuditLog(root / "audit.jsonl"),
            checkpoint_store=JsonCheckpointStore(root / "checkpoint.json"),
            audit_anchor_interval=1,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-watchdog-clock-001",
            recovery_sleep=lambda _: None,
            execution_max_seconds=5.0,
            monotonic=clock,
        )

    def approve(self, service):
        investigated = service.investigate()
        return service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator@example.com",
        )

    def test_invalid_start_clock_prevents_provider_dispatch(self):
        invalid_values = (
            True,
            float("nan"),
            float("inf"),
            float("-inf"),
            "100.0",
            RuntimeError("clock failed"),
        )
        for invalid in invalid_values:
            with self.subTest(invalid=repr(invalid)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                clock = MutableClock(invalid)
                remediation = CountingRemediation()
                service = self.service(root, clock, remediation)
                approved = self.approve(service)

                with self.assertRaisesRegex(
                    RuntimeError,
                    "remediation execution watchdog clock unavailable",
                ):
                    service.execute_approved(actor="operator@example.com")

                self.assertEqual(0, remediation.calls)
                self.assertEqual(approved, service.status())
                self.assertEqual("synchronized", service.checkpoint_state())
                self.assertFalse(service.remediation_execution_observability()["active"])

    def test_active_watchdog_clock_corruption_fails_deadline_closed(self):
        invalid_values = (
            True,
            float("nan"),
            float("inf"),
            float("-inf"),
            "100.0",
            RuntimeError("clock failed"),
        )
        for invalid in invalid_values:
            with self.subTest(invalid=repr(invalid)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                clock = MutableClock(100.0)
                service = self.service(root, clock, CountingRemediation())
                service._execution_in_flight = True
                service._execution_started_monotonic = 100.0

                clock.value = invalid
                observed = service.remediation_execution_observability()

                self.assertTrue(observed["active"])
                self.assertEqual(6.0, observed["age_seconds"])
                self.assertTrue(observed["deadline_exceeded"])
                self.assertEqual("execution_uncertain", service.checkpoint_state())

    def test_backward_active_clock_fails_deadline_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = MutableClock(100.0)
            service = self.service(root, clock, CountingRemediation())
            service._execution_in_flight = True
            service._execution_started_monotonic = 100.0

            clock.value = 99.999
            observed = service.remediation_execution_observability()

            self.assertEqual(6.0, observed["age_seconds"])
            self.assertTrue(observed["deadline_exceeded"])
            self.assertEqual("execution_uncertain", service.checkpoint_state())


if __name__ == "__main__":
    unittest.main()
