#!/usr/bin/env python3
from __future__ import annotations

import unittest

from runtime.timeline_projection import timeline_payload


class TimelinePolicyPresenceTests(unittest.TestCase):
    EVENT = "remediation_reconciliation_attempt.accepted.durable_dispatching"
    PAYLOAD = {"result": "accepted", "reason": "durable_dispatching"}

    def test_absent_policy_uses_canonical_reconciliation_projection(self) -> None:
        self.assertEqual(
            timeline_payload(self.EVENT, self.PAYLOAD, {}),
            {"result": "accepted", "reason": "durable_dispatching"},
        )

    def test_explicit_null_policy_fails_closed(self) -> None:
        self.assertEqual(
            timeline_payload(self.EVENT, self.PAYLOAD, {self.EVENT: None}),
            {},
        )

    def test_explicit_empty_policy_intentionally_discloses_nothing(self) -> None:
        self.assertEqual(
            timeline_payload(self.EVENT, self.PAYLOAD, {self.EVENT: ()}),
            {},
        )


if __name__ == "__main__":
    unittest.main()
