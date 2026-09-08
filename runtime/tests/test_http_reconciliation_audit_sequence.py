from __future__ import annotations

import signal
import shutil
import unittest

from incident_checkpoint import JsonCheckpointStore
from tests.test_http_subprocess_crash_recovery import build_service, diagnosed
from tests.test_http_subprocess_reconciliation_ambiguity import (
    HttpSubprocessReconciliationAmbiguityTests,
)


@unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires POSIX SIGKILL semantics")
@unittest.skipUnless(shutil.which("openssl"), "requires openssl to create an ephemeral test certificate")
class HttpReconciliationAuditSequenceTests(unittest.TestCase):
    """Bind bounded reconciliation audit semantics to the real TLS/crash path."""

    MODES = ("malformed", "wrong_operation_id", "unknown_state", "timeout")

    def test_audit_sequence_is_monotonic_and_remediation_is_never_replayed(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                harness = HttpSubprocessReconciliationAmbiguityTests(
                    "test_malformed_json_stays_execution_uncertain_until_valid_reconciliation"
                )
                harness.setUp()
                try:
                    harness.crash_after_provider_acceptance()
                    store = JsonCheckpointStore(harness.checkpoint_path)
                    before = store.load()
                    self.assertEqual("dispatching", before.execution_phase)

                    harness.server.reconciliation_mode = mode
                    restarted = build_service(
                        JsonCheckpointStore(harness.checkpoint_path),
                        harness.production_client(),
                        diagnosed(),
                    )
                    self.assertEqual("durable_dispatching", restarted.execution_reconciliation_reason())

                    with self.assertRaisesRegex(RuntimeError, "provider idempotency state is unresolved"):
                        restarted.reconcile_execution_uncertainty(actor="operator@example.com")

                    after_unknown = store.load()
                    self.assertEqual("dispatching", after_unknown.execution_phase)
                    self.assertGreater(after_unknown.sequence, before.sequence)
                    self.assertEqual(
                        ["remediation_reconciliation_attempt.unknown.durable_dispatching"],
                        [
                            event.event_type
                            for event in restarted._audit.events
                            if event.event_type.startswith("remediation_reconciliation_")
                        ],
                    )
                    self.assertEqual(1, len([event for event in harness.server.events if event[0] == "POST"]))
                    self.assertEqual(1, len([event for event in harness.server.events if event[0] == "GET"]))

                    harness.server.reconciliation_mode = "normal"
                    recovered = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
                    self.assertIsNone(recovered.approval)
                    self.assertEqual("clear", restarted.execution_reconciliation_reason())

                    after_recovery = store.load()
                    self.assertEqual("none", after_recovery.execution_phase)
                    self.assertGreater(after_recovery.sequence, after_unknown.sequence)
                    self.assertEqual(
                        [
                            "remediation_reconciliation_attempt.unknown.durable_dispatching",
                            "remediation_reconciliation_attempt.accepted.durable_dispatching",
                            "remediation_reconciliation_recovered.accepted.durable_dispatching",
                        ],
                        [
                            event.event_type
                            for event in restarted._audit.events
                            if event.event_type.startswith("remediation_reconciliation_")
                        ],
                    )
                    self.assertEqual(1, len([event for event in harness.server.events if event[0] == "POST"]))
                    self.assertEqual(2, len([event for event in harness.server.events if event[0] == "GET"]))

                    final_store = JsonCheckpointStore(harness.checkpoint_path)
                    final_restart = build_service(final_store, harness.production_client(), [])
                    final_checkpoint = final_store.load()
                    self.assertEqual(after_recovery.sequence, final_checkpoint.sequence)
                    self.assertEqual("none", final_checkpoint.execution_phase)
                    self.assertEqual("synchronized", final_restart.checkpoint_state())
                    self.assertEqual("clear", final_restart.execution_reconciliation_reason())
                    self.assertIsNone(final_restart.status().approval)
                    self.assertEqual(1, len([event for event in harness.server.events if event[0] == "POST"]))
                finally:
                    harness.tearDown()


if __name__ == "__main__":
    unittest.main()
