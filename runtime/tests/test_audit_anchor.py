from __future__ import annotations

import unittest

from audit_anchor import AuditAnchor, roll_audit_anchor, select_anchored_committed_lineage
from audit_integrity import AuditChain, AuditChainCheckpoint, GENESIS_SHA256
from incident_service import AuditEvent


def event(sequence: int, *, actor: str = "winner@example.com", event_type: str = "investigation_completed") -> AuditEvent:
    return AuditEvent(
        sequence,
        1_700_000_000_000 + sequence,
        "incident-1",
        event_type,
        actor,
        {"revision": f"rev-{sequence}"},
    )


def build_chain(count: int):
    chain = AuditChain()
    events = []
    checkpoints = {0: chain.checkpoint()}
    for sequence in range(1, count + 1):
        current = event(sequence)
        events.append(current)
        checkpoints[sequence] = chain.append(current)
    return events, checkpoints


class AuditAnchorTests(unittest.TestCase):
    def test_compacted_prefix_is_not_required_after_authenticated_anchor(self):
        events, checkpoints = build_chain(8)
        anchor = AuditAnchor.from_chain_checkpoint(checkpoints[4])

        selected = select_anchored_committed_lineage(
            events[4:], anchor=anchor, expected=checkpoints[8]
        )

        self.assertEqual([5, 6, 7, 8], [item.sequence for item in selected])

    def test_post_anchor_competitor_is_resolved_by_expected_head(self):
        events, checkpoints = build_chain(6)
        anchor = AuditAnchor.from_chain_checkpoint(checkpoints[3])
        competitor = event(5, actor="losing-writer@example.com")

        selected = select_anchored_committed_lineage(
            [events[3], competitor, events[4], events[5]],
            anchor=anchor,
            expected=checkpoints[6],
        )

        self.assertEqual([4, 5, 6], [item.sequence for item in selected])
        self.assertEqual("winner@example.com", selected[1].actor)

    def test_mutated_or_deleted_committed_suffix_fails_closed(self):
        events, checkpoints = build_chain(6)
        anchor = AuditAnchor.from_chain_checkpoint(checkpoints[3])
        mutated = event(5, actor="tampered@example.com")

        with self.assertRaisesRegex(ValueError, "integrity verification failed"):
            select_anchored_committed_lineage(
                [events[3], mutated, events[5]], anchor=anchor, expected=checkpoints[6]
            )
        with self.assertRaisesRegex(ValueError, "incomplete"):
            select_anchored_committed_lineage(
                [events[3], events[5]], anchor=anchor, expected=checkpoints[6]
            )

    def test_anchor_substitution_fails_closed(self):
        events, checkpoints = build_chain(6)
        wrong_anchor = AuditAnchor(3, checkpoints[2].head_sha256)

        with self.assertRaisesRegex(ValueError, "integrity verification failed"):
            select_anchored_committed_lineage(
                events[3:], anchor=wrong_anchor, expected=checkpoints[6]
            )

    def test_suffix_span_is_explicitly_bounded(self):
        events, checkpoints = build_chain(6)
        anchor = AuditAnchor.from_chain_checkpoint(checkpoints[2])

        with self.assertRaisesRegex(ValueError, "verification bound"):
            select_anchored_committed_lineage(
                events[2:], anchor=anchor, expected=checkpoints[6], max_suffix_events=3
            )

    def test_anchor_roll_requires_verified_monotonic_progress(self):
        _, checkpoints = build_chain(8)
        genesis = AuditAnchor.genesis()
        self.assertEqual(GENESIS_SHA256, genesis.head_sha256)

        unchanged = roll_audit_anchor(genesis, checkpoints[3], interval=4)
        self.assertEqual(genesis, unchanged)

        rolled = roll_audit_anchor(genesis, checkpoints[4], interval=4)
        self.assertEqual(4, rolled.sequence)
        self.assertEqual(checkpoints[4].head_sha256, rolled.head_sha256)

        with self.assertRaisesRegex(ValueError, "behind"):
            roll_audit_anchor(rolled, checkpoints[3], interval=4)
        with self.assertRaisesRegex(ValueError, "positive"):
            roll_audit_anchor(genesis, checkpoints[1], interval=0)

    def test_empty_suffix_requires_exact_anchor_head(self):
        _, checkpoints = build_chain(3)
        anchor = AuditAnchor.from_chain_checkpoint(checkpoints[3])
        self.assertEqual(
            [],
            select_anchored_committed_lineage([], anchor=anchor, expected=checkpoints[3]),
        )

        different = AuditChainCheckpoint(3, checkpoints[2].head_sha256)
        with self.assertRaisesRegex(ValueError, "integrity verification failed"):
            select_anchored_committed_lineage([], anchor=anchor, expected=different)


if __name__ == "__main__":
    unittest.main()
