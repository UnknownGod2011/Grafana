from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from incident_checkpoint import JsonCheckpointStore
from remediation import ActionResult


class RecheckBlockingMetrics:
    """Diagnosis + unverified first window, then block the recovery-only recheck."""

    def __init__(self):
        self.values = [
            4.0, 18.0, 41.0, 37.0, 0.2, 0.1,  # investigation
            *([8.0, 5.0] * 6),                 # first recovery window: unhealthy
            0.2, 0.2, 0.1, 0.1,               # recheck: two healthy samples
        ]
        self.index = 0
        self.recheck_entered = threading.Event()
        self.recheck_release = threading.Event()

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        if self.index == 18:
            self.recheck_entered.set()
            if not self.recheck_release.wait(timeout=2.0):
                raise RuntimeError("test recheck release timed out")
        value = self.values[self.index]
        self.index += 1
        return value


class CountingRemediation:
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


class AnchoredRecoveryRecheckTests(unittest.TestCase):
    def test_recheck_keeps_reads_responsive_blocks_mutations_and_never_replays_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics = RecheckBlockingMetrics()
            remediation = CountingRemediation()
            service = AnchoredExecutionSafeIncidentService(
                metrics,
                remediation,
                AnchoredJsonlAuditLog(root / "audit.jsonl"),
                checkpoint_store=JsonCheckpointStore(root / "checkpoint.json"),
                audit_anchor_interval=1,
                clock_ms=lambda: 123456789,
                id_factory=lambda: "incident-recheck-001",
                recovery_sleep=lambda _: None,
            )

            investigated = service.investigate()
            service.approve(
                incident_id=investigated.incident_id,
                revision=investigated.revision,
                approved_by="operator@example.com",
            )
            initial = service.execute_approved(actor="operator@example.com")
            self.assertEqual("recovery_unverified", initial.outcome.status)
            self.assertEqual(1, remediation.calls)

            result = {}
            errors = []

            def recheck():
                try:
                    result["snapshot"] = service.recheck_recovery(actor="operator@example.com")
                except Exception as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            worker = threading.Thread(target=recheck, daemon=True)
            worker.start()
            self.assertTrue(metrics.recheck_entered.wait(timeout=0.5), "recheck did not reach Grafana evidence read")

            read_done = threading.Event()
            read_result = {}

            def read_operator_state():
                read_result["snapshot"] = service.status()
                read_result["phase"] = service.execution_checkpoint_phase()
                read_result["watchdog"] = service.remediation_execution_observability()
                read_done.set()

            reader = threading.Thread(target=read_operator_state, daemon=True)
            reader.start()
            try:
                self.assertTrue(read_done.wait(timeout=0.25), "operator reads blocked behind recovery-only Grafana polling")
                self.assertEqual("recovery_unverified", read_result["snapshot"].outcome.status)
                self.assertEqual("resolved", read_result["phase"], "recovery-only verification must not look like provider dispatch")
                self.assertTrue(read_result["watchdog"]["active"])

                with self.assertRaisesRegex(RuntimeError, "already in progress"):
                    service.investigate()
                with self.assertRaisesRegex(RuntimeError, "already in progress"):
                    service.recheck_recovery(actor="operator@example.com")
                self.assertEqual(1, remediation.calls, "recovery recheck must never replay the provider action")
            finally:
                metrics.recheck_release.set()

            worker.join(timeout=1.0)
            reader.join(timeout=1.0)
            self.assertFalse(worker.is_alive(), "recheck worker did not finish")
            self.assertEqual([], errors)
            self.assertEqual("recovered", result["snapshot"].outcome.status)
            self.assertEqual(1, remediation.calls)
            self.assertFalse(service.remediation_execution_observability()["active"])
            self.assertEqual("resolved", service.execution_checkpoint_phase())

    def test_recheck_metric_failure_does_not_create_provider_execution_uncertainty(self):
        class FailingMetrics:
            def __init__(self):
                self.values = [4.0, 18.0, 41.0, 37.0, 0.2, 0.1, *([8.0, 5.0] * 6)]
                self.index = 0

            def instant(self, _query):
                if self.index < len(self.values):
                    value = self.values[self.index]
                    self.index += 1
                    return value
                raise RuntimeError("grafana unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics = FailingMetrics()
            remediation = CountingRemediation()
            service = AnchoredExecutionSafeIncidentService(
                metrics,
                remediation,
                AnchoredJsonlAuditLog(root / "audit.jsonl"),
                checkpoint_store=JsonCheckpointStore(root / "checkpoint.json"),
                audit_anchor_interval=1,
                clock_ms=lambda: 123456789,
                id_factory=lambda: "incident-recheck-002",
                recovery_sleep=lambda _: None,
            )
            investigated = service.investigate()
            service.approve(
                incident_id=investigated.incident_id,
                revision=investigated.revision,
                approved_by="operator@example.com",
            )
            self.assertEqual("recovery_unverified", service.execute_approved().outcome.status)

            with self.assertRaisesRegex(RuntimeError, "grafana unavailable"):
                service.recheck_recovery()

            self.assertEqual(1, remediation.calls)
            self.assertEqual("clear", service.execution_reconciliation_state())
            self.assertEqual("synchronized", service.checkpoint_state())
            self.assertEqual("recovery_unverified", service.status().outcome.status)
            self.assertFalse(service.remediation_execution_observability()["active"])


if __name__ == "__main__":
    unittest.main()
