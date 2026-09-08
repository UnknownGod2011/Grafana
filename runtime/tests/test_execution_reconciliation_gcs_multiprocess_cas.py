import multiprocessing
import os
import unittest

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import CheckpointConflictError, GoogleCloudStorageCheckpointStore, IncidentCheckpoint
from incident_service import MemoryAuditLog
from remediation import ActionResult
from test_execution_gcs_multiprocess_cas import approved_checkpoint
from test_gcs_multiprocess_cas import KEY, OBJECT, SharedBucket


class TaggedFreshEvidence:
    """Six bounded Grafana/Prometheus reads with a process-distinct revision."""

    def __init__(self, tag):
        cpu = 20.0 if tag == "a" else 21.0
        self.values = [0.2, 0.0, cpu, 20.0, 0.1, 0.1]
        self.index = 0

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class ReconciliationOnlyRemediation:
    requires_operation_reconciliation = True

    def __init__(self, tag, barrier, reconciliation_calls, provider_calls):
        self._tag = tag
        self._barrier = barrier
        self._reconciliation_calls = reconciliation_calls
        self._provider_calls = provider_calls

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self._provider_calls.append((self._tag, production_id, uplink, operation_id))
        raise AssertionError("reconciliation must never execute remediation")

    def recover_uplink(self, production_id, uplink):
        self._provider_calls.append((self._tag, production_id, uplink, "legacy"))
        raise AssertionError("reconciliation must never execute remediation")

    def reconcile_operation(self, operation_id):
        self._reconciliation_calls.append((self._tag, operation_id))
        self._barrier.wait()
        return "accepted"


def dispatching_checkpoint():
    approved = approved_checkpoint()
    return IncidentCheckpoint(
        approved.incident_id,
        approved.revision,
        approved.report,
        approved.approval,
        approved.outcome,
        approved.sequence,
        "dispatching",
    )


def _reconciliation_racer(
    tag,
    state,
    lock,
    reconcile_barrier,
    reload_event,
    reconciliation_calls,
    provider_calls,
    results,
):
    store = GoogleCloudStorageCheckpointStore(SharedBucket(state, lock), KEY, OBJECT)
    remediation = ReconciliationOnlyRemediation(tag, reconcile_barrier, reconciliation_calls, provider_calls)
    service = ExecutionSafeIncidentService(
        TaggedFreshEvidence(tag),
        remediation,
        MemoryAuditLog(),
        checkpoint_store=store,
        clock_ms=lambda: 123456789,
        id_factory=lambda: "incident-001",
        recovery_sleep=lambda _: None,
    )
    snapshot = service.status()
    results.put(
        (
            tag,
            "loaded",
            snapshot.approval is not None,
            service.checkpoint_state(),
            service.execution_checkpoint_phase(),
            service.execution_reconciliation_state(),
        )
    )

    try:
        reconciled = service.reconcile_execution_uncertainty(actor=f"{tag}@example.com")
    except CheckpointConflictError:
        results.put(
            (
                tag,
                "reconcile",
                "conflict",
                service.checkpoint_state(),
                service.execution_checkpoint_phase(),
                service.status().revision,
            )
        )
        reload_event.wait(10)
        adopted = service.reload_checkpoint_after_conflict()
        results.put(
            (
                tag,
                "reload",
                adopted.revision,
                adopted.approval is None,
                service.checkpoint_state(),
                service.execution_checkpoint_phase(),
                service.execution_reconciliation_state(),
            )
        )
        try:
            service.reconcile_execution_uncertainty(actor=f"{tag}@example.com")
        except RuntimeError as exc:
            results.put((tag, "second-reconcile", str(exc)))
        else:
            results.put((tag, "second-reconcile", "unexpected-success"))
    else:
        results.put(
            (
                tag,
                "reconcile",
                "winner",
                reconciled.revision,
                reconciled.approval is None,
                reconciled.report.status,
                service.checkpoint_state(),
                service.execution_checkpoint_phase(),
                service.execution_reconciliation_state(),
            )
        )


@unittest.skipUnless(os.name == "posix", "multiprocess reconciliation CAS acceptance requires POSIX process support")
class ExecutionReconciliationGcsMultiprocessCasAcceptanceTests(unittest.TestCase):
    def test_one_reconciliation_evidence_revision_wins_and_stale_reconciler_adopts_it_without_replay(self):
        ctx = multiprocessing.get_context("spawn")
        with ctx.Manager() as manager:
            state = manager.dict(data=b"", generation=0)
            lock = manager.RLock()
            reconciliation_calls = manager.list()
            provider_calls = manager.list()
            bucket = SharedBucket(state, lock)

            seed = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            seed.save(dispatching_checkpoint())
            self.assertEqual(1, int(state["generation"]))

            reconcile_barrier = ctx.Barrier(2)
            reload_event = ctx.Event()
            results = ctx.Queue()
            workers = [
                ctx.Process(
                    target=_reconciliation_racer,
                    args=(
                        "a",
                        state,
                        lock,
                        reconcile_barrier,
                        reload_event,
                        reconciliation_calls,
                        provider_calls,
                        results,
                    ),
                ),
                ctx.Process(
                    target=_reconciliation_racer,
                    args=(
                        "b",
                        state,
                        lock,
                        reconcile_barrier,
                        reload_event,
                        reconciliation_calls,
                        provider_calls,
                        results,
                    ),
                ),
            ]
            for worker in workers:
                worker.start()

            loaded = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual({"a", "b"}, {item[0] for item in loaded})
            for item in loaded:
                self.assertEqual("loaded", item[1])
                self.assertTrue(item[2])
                self.assertEqual("execution_uncertain", item[3])
                self.assertEqual("dispatching", item[4])
                self.assertEqual("reloaded", item[5])

            raced = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual({"winner", "conflict"}, {item[2] for item in raced})
            winner = next(item for item in raced if item[2] == "winner")
            loser = next(item for item in raced if item[2] == "conflict")
            winning_revision = winner[3]

            self.assertTrue(winner[4])
            self.assertEqual("no_incident", winner[5])
            self.assertEqual("synchronized", winner[6])
            self.assertEqual("none", winner[7])
            self.assertEqual("clear", winner[8])
            self.assertEqual("execution_uncertain", loser[3])
            self.assertEqual("dispatching", loser[4])

            # Both instances may read the provider's idempotency state, but neither
            # is permitted to execute remediation during reconciliation.
            self.assertEqual(2, len(reconciliation_calls))
            self.assertEqual(0, len(provider_calls))

            # Only one fresh Grafana evidence write may win generation CAS.
            self.assertEqual(2, int(state["generation"]))
            durable = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            recovered = durable.load()
            self.assertEqual(winning_revision, recovered.revision)
            self.assertIsNone(recovered.approval)
            self.assertIsNone(recovered.outcome)
            self.assertEqual("none", recovered.execution_phase)
            self.assertEqual("no_incident", recovered.report.status)

            # After the winning evidence revision is durable, the stale reconciler
            # explicitly reloads it. Its process-local ambiguity must be rebased
            # from that authenticated winner rather than forcing another provider
            # reconciliation or another evidence write.
            reload_event.set()
            reload_result = results.get(timeout=10)
            self.assertEqual(loser[0], reload_result[0])
            self.assertEqual("reload", reload_result[1])
            self.assertEqual(winning_revision, reload_result[2])
            self.assertTrue(reload_result[3])
            self.assertEqual("synchronized", reload_result[4])
            self.assertEqual("none", reload_result[5])
            self.assertEqual("clear", reload_result[6])

            second = results.get(timeout=10)
            self.assertEqual(loser[0], second[0])
            self.assertEqual("second-reconcile", second[1])
            self.assertIn("no uncertain remediation execution", second[2])
            self.assertEqual(2, len(reconciliation_calls))
            self.assertEqual(0, len(provider_calls))
            self.assertEqual(2, int(state["generation"]))

            for worker in workers:
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(0, worker.exitcode)

            # A clean third instance must adopt exactly the winning Grafana evidence
            # revision with no stale approval and no reconciliation requirement.
            verifier_service = ExecutionSafeIncidentService(
                TaggedFreshEvidence("a"),
                ReconciliationOnlyRemediation("verifier", ctx.Barrier(1), reconciliation_calls, provider_calls),
                MemoryAuditLog(),
                checkpoint_store=GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT),
                clock_ms=lambda: 123456789,
                id_factory=lambda: "incident-001",
                recovery_sleep=lambda _: None,
            )
            final = verifier_service.status()
            self.assertEqual(winning_revision, final.revision)
            self.assertIsNone(final.approval)
            self.assertEqual("synchronized", verifier_service.checkpoint_state())
            self.assertEqual("none", verifier_service.execution_checkpoint_phase())
            self.assertEqual("clear", verifier_service.execution_reconciliation_state())
            self.assertEqual(2, len(reconciliation_calls))
            self.assertEqual(0, len(provider_calls))


if __name__ == "__main__":
    unittest.main()
