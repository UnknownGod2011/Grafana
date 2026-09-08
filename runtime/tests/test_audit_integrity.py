from __future__ import annotations

import unittest

from audit_integrity import (
    GENESIS_SHA256,
    AuditChain,
    AuditChainCheckpoint,
    ChainedAuditSink,
    extend_audit_chain,
    verify_audit_chain,
)
from incident_service import AuditEvent


def event(sequence: int, *, payload: dict | None = None) -> AuditEvent:
    return AuditEvent(
        sequence,
        1_700_000_000_000 + sequence,
        "incident-1",
        "remediation_reconciliation_attempt.unknown.durable_dispatching",
        "operator@example.com",
        payload or {"result": "unknown", "reason": "durable_dispatching"},
    )


class CollectingSink:
    def __init__(self, fail: bool = False) -> None:
        self.events: list[AuditEvent] = []
        self.fail = fail

    def append(self, audit_event: AuditEvent) -> None:
        if self.fail:
            raise RuntimeError("sink unavailable")
        self.events.append(audit_event)


class AuditIntegrityTests(unittest.TestCase):
    def test_chain_is_deterministic_and_restart_continuable(self):
        first = event(1)
        second = event(2, payload={"result": "accepted", "reason": "durable_dispatching"})

        chain = AuditChain()
        first_checkpoint = chain.append(first)
        final_checkpoint = chain.append(second)

        restarted = AuditChain(first_checkpoint)
        self.assertEqual(final_checkpoint, restarted.append(second))
        self.assertEqual(
            extend_audit_chain(first_checkpoint.head_sha256, second),
            final_checkpoint.head_sha256,
        )
        self.assertNotEqual(GENESIS_SHA256, final_checkpoint.head_sha256)

    def test_verifier_detects_deletion_reordering_and_mutation(self):
        events = [event(1), event(2), event(3)]
        chain = AuditChain()
        for item in events:
            expected = chain.append(item)

        self.assertEqual(expected, verify_audit_chain(events, expected))

        with self.assertRaisesRegex(ValueError, "sequence is not contiguous"):
            verify_audit_chain([events[0], events[2]], expected)
        with self.assertRaisesRegex(ValueError, "sequence is not contiguous"):
            verify_audit_chain([events[1], events[0], events[2]], expected)

        mutated = [events[0], event(2, payload={"result": "not_found", "reason": "durable_dispatching"}), events[2]]
        with self.assertRaisesRegex(ValueError, "integrity verification failed"):
            verify_audit_chain(mutated, expected)

    def test_verifier_supports_bounded_restart_from_trusted_checkpoint(self):
        chain = AuditChain()
        checkpoint_two = None
        events = [event(i) for i in range(1, 6)]
        for item in events:
            current = chain.append(item)
            if item.sequence == 2:
                checkpoint_two = current
        self.assertIsNotNone(checkpoint_two)
        final = chain.checkpoint()

        self.assertEqual(
            final,
            verify_audit_chain(events[2:], final, initial=checkpoint_two),
        )

    def test_sink_failure_does_not_publish_unwritten_chain_head(self):
        inner = CollectingSink(fail=True)
        sink = ChainedAuditSink(inner)

        with self.assertRaisesRegex(RuntimeError, "sink unavailable"):
            sink.append(event(1))

        self.assertEqual(AuditChainCheckpoint(0, GENESIS_SHA256), sink.checkpoint())
        self.assertEqual([], inner.events)

        inner.fail = False
        sink.append(event(1))
        self.assertEqual(1, sink.checkpoint().sequence)
        self.assertEqual([event(1)], inner.events)

    def test_invalid_checkpoint_and_non_contiguous_append_fail_closed(self):
        with self.assertRaises(ValueError):
            AuditChainCheckpoint(0, "f" * 64)
        with self.assertRaises(ValueError):
            AuditChainCheckpoint(1, "not-a-digest")

        chain = AuditChain()
        with self.assertRaisesRegex(ValueError, "sequence is not contiguous"):
            chain.append(event(2))
        self.assertEqual(AuditChainCheckpoint(0, GENESIS_SHA256), chain.checkpoint())


if __name__ == "__main__":
    unittest.main()
