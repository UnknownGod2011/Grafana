import multiprocessing
import os
import unittest

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import CheckpointConflictError, GoogleCloudStorageCheckpointStore, IncidentCheckpoint
from incident_service import MemoryAuditLog
from remediation import ActionResult, Approval
from test_gcs_multiprocess_cas import KEY, OBJECT, SharedBlob, SharedBucket, checkpoint


class RecoveryMetrics:
    """Fixed healthy Grafana/Prometheus samples used only after provider acceptance."""

    def __init__(self):
        self.values = [0.2, 0.2, 0.1, 0.1]
        self.index = 0

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class SharedCountingRemediation:
    requires_operation_reconciliation = True

    def __init__(self, provider_calls):
        self._provider_calls = provider_calls

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self._provider_calls.append((production_id, uplink, operation_id))
        return ActionResult(True, "accepted", {})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("idempotent production path required")

    def reconcile_operation(self, operation_id):
        return "accepted"


def approved_checkpoint(sequence=2):
    base = checkpoint(sequence)
    approval = Approval(True, "operator@example.com", "recover_uplink", base.report.production_id, "uplink-b")
    return IncidentCheckpoint(
        base.incident_id,
        base.revision,
        base.report,
        approval,
        None,
        sequence,
        "approved",
    )


def _service_racer(tag, state, lock, barrier, retry_event, provider_calls, results):
    """Restore one approved generation, race dispatch, then make the loser retry stale."""
    store = GoogleCloudStorageCheckpointStore(SharedBucket(state, lock), KEY, OBJECT)
    remediation = SharedCountingRemediation(provider_calls)
    service = ExecutionSafeIncidentService(
        RecoveryMetrics(),
        remediation,
        MemoryAuditLog(),
        checkpoint_store=store,
        clock_ms=lambda: 123456789,
        id_factory=lambda: "incident-001",
        recovery_sleep=lambda _: None,
    )
    snapshot = service.status()
    results.put((tag, "loaded", snapshot.approval is not None, service.execution_checkpoint_phase()))
    barrier.wait()

    try:
        completed = service.execute_approved(actor=f"{tag}@example.com")
    except CheckpointConflictError:
        results.put((tag, "first", "conflict", service.checkpoint_state(), len(provider_calls)))
        retry_event.wait(10)
        try:
            service.execute_approved(actor=f"{tag}@example.com")
        except CheckpointConflictError:
            results.put((tag, "retry", "conflict", service.checkpoint_state(), len(provider_calls)))
        except Exception as exc:
            results.put((tag, "retry", type(exc).__name__, service.checkpoint_state(), len(provider_calls)))
        else:
            results.put((tag, "retry", "unexpected-success", service.checkpoint_state(), len(provider_calls)))
    else:
        results.put((tag, "first", completed.outcome.status, service.checkpoint_state(), len(provider_calls)))


@unittest.skipUnless(os.name == "posix", "multiprocess execution CAS acceptance requires POSIX process support")
class ExecutionGcsMultiprocessCasAcceptanceTests(unittest.TestCase):
    def test_only_dispatching_cas_winner_can_contact_provider_and_stale_loser_never_replays(self):
        ctx = multiprocessing.get_context("spawn")
        with ctx.Manager() as manager:
            state = manager.dict(data=b"", generation=0)
            lock = manager.RLock()
            provider_calls = manager.list()
            bucket = SharedBucket(state, lock)

            seed = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            seed.save(approved_checkpoint())
            self.assertEqual(1, int(state["generation"]))

            barrier = ctx.Barrier(2)
            retry_event = ctx.Event()
            results = ctx.Queue()
            workers = [
                ctx.Process(target=_service_racer, args=("a", state, lock, barrier, retry_event, provider_calls, results)),
                ctx.Process(target=_service_racer, args=("b", state, lock, barrier, retry_event, provider_calls, results)),
            ]
            for worker in workers:
                worker.start()

            loaded = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual(
                {("a", "loaded", True, "approved"), ("b", "loaded", True, "approved")},
                set(loaded),
            )

            first = [results.get(timeout=10), results.get(timeout=10)]
            outcomes = {item[2] for item in first}
            self.assertEqual({"recovered", "conflict"}, outcomes)
            loser = next(item for item in first if item[2] == "conflict")
            self.assertEqual("conflicted", loser[3])

            # Exactly one service crossed the durable dispatch barrier and therefore
            # exactly one remediation operation reached the provider.
            self.assertEqual(1, len(provider_calls))
            self.assertEqual(3, int(state["generation"]))  # approved -> dispatching -> resolved

            durable = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            resolved = durable.load()
            self.assertIsNotNone(resolved.outcome)
            self.assertEqual("resolved", resolved.execution_phase)
            self.assertEqual("recovered", resolved.outcome.status)

            # Release the losing process only after recovery is durable. Its store
            # still holds the original approved generation, so another dispatch
            # attempt must lose CAS again before provider contact.
            retry_event.set()
            retry = results.get(timeout=10)
            self.assertEqual(loser[0], retry[0])
            self.assertEqual("retry", retry[1])
            self.assertEqual("conflict", retry[2])
            self.assertEqual("conflicted", retry[3])
            self.assertEqual(1, len(provider_calls))

            for worker in workers:
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(0, worker.exitcode)

            verifier = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            final = verifier.load()
            self.assertEqual("resolved", final.execution_phase)
            self.assertEqual("recovered", final.outcome.status)
            self.assertEqual(3, int(state["generation"]))
            self.assertEqual(1, len(provider_calls))


if __name__ == "__main__":
    unittest.main()
