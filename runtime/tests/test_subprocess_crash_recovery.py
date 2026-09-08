import multiprocessing
import os
import signal
import tempfile
import unittest
from pathlib import Path

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import JsonCheckpointStore
from incident_service import MemoryAuditLog


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


class NoopProductionRemediation:
    """Production-shaped adapter used only to create an approved checkpoint."""

    requires_operation_reconciliation = True

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        raise AssertionError("setup must not execute remediation")

    def reconcile_operation(self, operation_id):
        return "not_found"


def hard_kill():
    os.kill(os.getpid(), signal.SIGKILL)
    os._exit(93)


class CrashRemediation:
    """Adapter that SIGKILLs the process at a precise side-effect boundary."""

    requires_operation_reconciliation = True

    def __init__(self, checkpoint_path, call_log_path, crash_mode):
        self.checkpoint_path = checkpoint_path
        self.call_log_path = call_log_path
        self.crash_mode = crash_mode

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        checkpoint = JsonCheckpointStore(self.checkpoint_path).load()
        if checkpoint is None or checkpoint.execution_phase != "dispatching":
            os._exit(90)
        if self.crash_mode == "after_dispatching_before_provider_acceptance":
            hard_kill()
        if self.crash_mode != "after_provider_acceptance":
            os._exit(91)
        with open(self.call_log_path, "a", encoding="utf-8") as handle:
            handle.write(operation_id + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Model a provider that accepted the operation immediately before the
        # StageGuard worker is killed and therefore cannot return to the caller.
        hard_kill()

    def reconcile_operation(self, operation_id):
        raise AssertionError("crashing child must not reconcile")


class ReconcileOnlyRemediation:
    requires_operation_reconciliation = True

    def __init__(self, call_log_path, provider_state):
        self.call_log_path = call_log_path
        self.provider_state = provider_state
        self.execute_calls = []
        self.reconcile_calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.execute_calls.append(operation_id)
        raise AssertionError("restart recovery must never replay remediation")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return self.provider_state


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def build_service(store, remediation, values):
    return ExecutionSafeIncidentService(
        SequenceMetrics(values),
        remediation,
        MemoryAuditLog(),
        checkpoint_store=store,
        clock_ms=lambda: 123456789,
        id_factory=lambda: "incident-subprocess-001",
        recovery_sleep=lambda _: None,
    )


def crash_child(checkpoint_path, call_log_path, crash_mode):
    store = JsonCheckpointStore(checkpoint_path)
    remediation = CrashRemediation(checkpoint_path, call_log_path, crash_mode)
    service = build_service(store, remediation, [])
    service.execute_approved(actor="subprocess-operator@example.com")
    os._exit(92)


@unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires POSIX SIGKILL semantics")
class SubprocessCrashRecoveryTests(unittest.TestCase):
    def prepare_approved_checkpoint(self, checkpoint_path):
        store = JsonCheckpointStore(checkpoint_path)
        service = build_service(store, NoopProductionRemediation(), diagnosed())
        snapshot = service.investigate(actor="setup@example.com")
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        checkpoint = store.load()
        self.assertIsNotNone(checkpoint)
        self.assertEqual("approved", checkpoint.execution_phase)
        return store

    @staticmethod
    def provider_calls(path):
        if not Path(path).exists():
            return []
        return [line for line in Path(path).read_text(encoding="utf-8").splitlines() if line]

    def run_crash_case(self, crash_mode, expected_provider_calls, provider_state):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = str(Path(tmp) / "incident.json")
            call_log_path = str(Path(tmp) / "provider-calls.log")
            self.prepare_approved_checkpoint(checkpoint_path)

            context = multiprocessing.get_context("spawn")
            process = context.Process(
                target=crash_child,
                args=(checkpoint_path, call_log_path, crash_mode),
            )
            process.start()
            process.join(10)
            if process.is_alive():
                process.kill()
                process.join(5)
                self.fail("crash child did not terminate at the injected boundary")
            self.assertEqual(-signal.SIGKILL, process.exitcode)

            durable = JsonCheckpointStore(checkpoint_path).load()
            self.assertIsNotNone(durable)
            self.assertEqual("dispatching", durable.execution_phase)
            calls_before_restart = self.provider_calls(call_log_path)
            self.assertEqual(expected_provider_calls, len(calls_before_restart))

            remediation = ReconcileOnlyRemediation(call_log_path, provider_state)
            restarted = build_service(JsonCheckpointStore(checkpoint_path), remediation, diagnosed())
            self.assertEqual("execution_uncertain", restarted.checkpoint_state())
            self.assertEqual("dispatching", restarted.execution_checkpoint_phase())
            self.assertEqual("reloaded", restarted.execution_reconciliation_state())

            refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
            self.assertEqual(1, len(remediation.reconcile_calls))
            self.assertEqual([], remediation.execute_calls)
            self.assertIsNone(refreshed.approval)
            self.assertEqual("none", restarted.execution_checkpoint_phase())
            self.assertEqual("synchronized", restarted.checkpoint_state())
            self.assertEqual(calls_before_restart, self.provider_calls(call_log_path))

            # A subsequent restart must remain non-executable until a human
            # explicitly approves the fresh Grafana evidence revision.
            final_adapter = ReconcileOnlyRemediation(call_log_path, "not_found")
            final_restart = build_service(JsonCheckpointStore(checkpoint_path), final_adapter, [])
            self.assertEqual("synchronized", final_restart.checkpoint_state())
            self.assertIsNone(final_restart.status().approval)
            self.assertEqual([], final_adapter.execute_calls)
            self.assertEqual(calls_before_restart, self.provider_calls(call_log_path))

    def test_sigkill_after_dispatching_before_provider_acceptance_never_executes(self):
        self.run_crash_case(
            "after_dispatching_before_provider_acceptance",
            expected_provider_calls=0,
            provider_state="not_found",
        )

    def test_sigkill_after_provider_acceptance_never_replays(self):
        self.run_crash_case(
            "after_provider_acceptance",
            expected_provider_calls=1,
            provider_state="accepted",
        )


if __name__ == "__main__":
    unittest.main()
