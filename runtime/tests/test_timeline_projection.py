#!/usr/bin/env python3
from __future__ import annotations

import unittest

from runtime.timeline_projection import reconciliation_timeline_payload


class ReconciliationTimelineProjectionTests(unittest.TestCase):
    def test_projects_only_bounded_result_and_reason(self) -> None:
        projected = reconciliation_timeline_payload(
            "remediation_reconciliation_attempt.accepted.durable_dispatching",
            {
                "result": "accepted",
                "reason": "durable_dispatching",
                "operation_id": "sg-secret-operation-reference",
                "provider_body": {"token": "must-not-leak"},
                "target": "production-feed",
            },
        )
        self.assertEqual(
            projected,
            {"result": "accepted", "reason": "durable_dispatching"},
        )

    def test_supports_all_current_bounded_states(self) -> None:
        for result in ("accepted", "not_found", "unknown"):
            for reason in (
                "durable_dispatching",
                "legacy_unknown",
                "post_dispatch_checkpoint_regression",
                "phase_unavailable",
            ):
                with self.subTest(result=result, reason=reason):
                    self.assertEqual(
                        reconciliation_timeline_payload(
                            f"remediation_reconciliation_recovered.{result}.{reason}",
                            {"result": result, "reason": reason},
                        ),
                        {"result": result, "reason": reason},
                    )

    def test_non_reconciliation_event_fails_closed(self) -> None:
        self.assertEqual(
            reconciliation_timeline_payload(
                "remediation_completed",
                {"result": "accepted", "reason": "durable_dispatching"},
            ),
            {},
        )

    def test_unbounded_or_future_values_fail_closed(self) -> None:
        self.assertEqual(
            reconciliation_timeline_payload(
                "remediation_reconciliation_attempt.accepted.future_reason",
                {"result": "accepted", "reason": "future_reason"},
            ),
            {},
        )
        self.assertEqual(
            reconciliation_timeline_payload(
                "remediation_reconciliation_attempt.future.durable_dispatching",
                {"result": "future", "reason": "durable_dispatching"},
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()
