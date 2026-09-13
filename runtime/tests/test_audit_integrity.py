from __future__ import annotations

import math
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

    def test_non_finite_payload_numbers_are_not_canonicalizable(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                chain = AuditChain()
                with self.assertRaisesRegex(ValueError, "not canonically serializable"):
                    chain.append(event(1, payload={"value": value}))
                self.assertEqual(
                    AuditChainCheckpoint(0, GENESIS_SHA256),
                    chain.checkpoint(),
                )

    def test_nested_non_finite_payload_numbers_are_not_canonicalizable(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "not canonically serializable"):
                    extend_audit_chain(
                        GENESIS_SHA256,
                        event(1, payload={"evidence": {"sample": value}}),
                    )

    def test_finite_numeric_payload_remains_canonicalizable(self):
        checkpoint = AuditChain().append(
            event(
                1,
                payload={
                    "confidence": 0.875,
                    "sample_count": 4,
                    "nested": {"latency_ms": 12.5},
                },
            )
        )
        self.assertEqual(1, checkpoint.sequence)
        self.assertNotEqual(GENESIS_SHA256, checkpoint.head_sha256)

    def test_envelope_controls_are_not_authenticatable(self):
        base = event(1)
        cases = (
            AuditEvent(base.sequence, base.timestamp_unix_ms, "incident\n1", base.event_type, base.actor, base.payload),
            AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, "remediation\x00completed", base.actor, base.payload),
            AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, base.event_type, "operator\x1b@example.com", base.payload),
            AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, base.event_type, "operator\x7f@example.com", base.payload),
        )
        for malformed in cases:
            with self.subTest(event=malformed):
                chain = AuditChain()
                with self.assertRaisesRegex(ValueError, "invalid audit"):
                    chain.append(malformed)
                self.assertEqual(AuditChainCheckpoint(0, GENESIS_SHA256), chain.checkpoint())

    def test_envelope_values_are_bounded_in_utf8_bytes(self):
        base = event(1)
        cases = (
            ("incident_id", AuditEvent(base.sequence, base.timestamp_unix_ms, "é" * 129, base.event_type, base.actor, base.payload)),
            ("event_type", AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, "é" * 65, base.actor, base.payload)),
            ("actor", AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, base.event_type, "é" * 257, base.payload)),
        )
        for field, malformed in cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"invalid audit {field}"):
                    extend_audit_chain(GENESIS_SHA256, malformed)

    def test_exact_envelope_utf8_limits_remain_authenticatable(self):
        valid = AuditEvent(
            1,
            1_700_000_000_001,
            "é" * 128,
            "é" * 64,
            "é" * 256,
            {"result": "unknown"},
        )
        checkpoint = AuditChain().append(valid)
        self.assertEqual(1, checkpoint.sequence)
        self.assertNotEqual(GENESIS_SHA256, checkpoint.head_sha256)

    def test_non_string_envelope_values_fail_with_stable_value_error(self):
        base = event(1)
        cases = (
            AuditEvent(base.sequence, base.timestamp_unix_ms, 7, base.event_type, base.actor, base.payload),
            AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, True, base.actor, base.payload),
            AuditEvent(base.sequence, base.timestamp_unix_ms, base.incident_id, base.event_type, object(), base.payload),
        )
        for malformed in cases:
            with self.subTest(event=malformed):
                with self.assertRaisesRegex(ValueError, "invalid audit"):
                    extend_audit_chain(GENESIS_SHA256, malformed)


if __name__ == "__main__":
    unittest.main()
