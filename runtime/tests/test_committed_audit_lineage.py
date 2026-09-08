from __future__ import annotations

import unittest

from audit_integrity import AuditChain, AuditChainCheckpoint, verify_committed_audit_lineage
from incident_service import AuditEvent


def event(sequence: int, actor: str = "stageguard", *, event_type: str = "investigation_completed") -> AuditEvent:
    return AuditEvent(
        sequence=sequence,
        timestamp_unix_ms=1000 + sequence,
        incident_id="incident-001",
        event_type=event_type,
        actor=actor,
        payload={"revision": "0123456789abcdef"},
    )


def committed(*events: AuditEvent) -> AuditChainCheckpoint:
    chain = AuditChain()
    for item in events:
        chain.append(item)
    return chain.checkpoint()


class CommittedAuditLineageTests(unittest.TestCase):
    def test_selects_checkpoint_committed_event_among_same_sequence_competitors(self):
        winner = event(1, "winner")
        loser = event(1, "loser")
        expected = committed(winner)

        self.assertEqual(expected, verify_committed_audit_lineage([loser, winner], expected))
        self.assertEqual(expected, verify_committed_audit_lineage([winner, loser], expected))

    def test_ignores_uncommitted_tail_beyond_authenticated_head(self):
        winner = event(1, "winner")
        expected = committed(winner)
        orphan = event(2, "crashed-writer", event_type="remediation_approved")

        self.assertEqual(expected, verify_committed_audit_lineage([winner, orphan], expected))

    def test_competing_branch_can_rejoin_only_if_authenticated_head_matches(self):
        first = event(1, "winner-1")
        second = event(2, "winner-2")
        expected = committed(first, second)
        losing_first = event(1, "loser-1")
        losing_second = event(2, "loser-2")

        self.assertEqual(
            expected,
            verify_committed_audit_lineage([losing_first, first, losing_second, second], expected),
        )

    def test_mutation_of_only_committed_candidate_fails_closed(self):
        original = event(1, "winner")
        expected = committed(original)
        mutated = event(1, "tampered")

        with self.assertRaisesRegex(ValueError, "integrity verification failed"):
            verify_committed_audit_lineage([mutated], expected)

    def test_deletion_of_committed_sequence_fails_closed(self):
        first = event(1, "winner-1")
        second = event(2, "winner-2")
        expected = committed(first, second)

        with self.assertRaisesRegex(ValueError, "incomplete"):
            verify_committed_audit_lineage([second], expected)

    def test_candidate_explosion_fails_closed(self):
        winner = event(1, "winner")
        expected = committed(winner)
        candidates = [event(1, f"writer-{index}") for index in range(4)]

        with self.assertRaisesRegex(ValueError, "too many competing events"):
            verify_committed_audit_lineage(candidates, expected, max_candidates_per_sequence=3)

    def test_state_explosion_fails_closed(self):
        first = event(1, "winner-1")
        second = event(2, "winner-2")
        expected = committed(first, second)
        candidates = [
            event(1, "a"),
            event(1, "b"),
            event(2, "c"),
            event(2, "d"),
        ]

        with self.assertRaisesRegex(ValueError, "safe bound"):
            verify_committed_audit_lineage(candidates, expected, max_states=2)

    def test_can_continue_from_trusted_intermediate_checkpoint(self):
        first = event(1, "winner-1")
        second = event(2, "winner-2")
        third = event(3, "winner-3")
        initial = committed(first)
        chain = AuditChain(initial)
        chain.append(second)
        chain.append(third)
        expected = chain.checkpoint()

        self.assertEqual(
            expected,
            verify_committed_audit_lineage([event(2, "loser"), second, third], expected, initial=initial),
        )


if __name__ == "__main__":
    unittest.main()
