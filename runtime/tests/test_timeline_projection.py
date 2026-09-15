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
        self.assertEqual(projected, {"result": "accepted", "reason": "durable_dispatching"})

    def test_supports_all_current_bounded_states(self) -> None:
        for stage in ("attempt", "recovered"):
            for result in ("accepted", "not_found", "unknown"):
                for reason in (
                    "durable_dispatching",
                    "legacy_unknown",
                    "post_dispatch_checkpoint_regression",
                    "phase_unavailable",
                ):
                    with self.subTest(stage=stage, result=result, reason=reason):
                        self.assertEqual(
                            reconciliation_timeline_payload(
                                f"remediation_reconciliation_{stage}.{result}.{reason}",
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
        for event_type, payload in (
            (
                "remediation_reconciliation_attempt.accepted.future_reason",
                {"result": "accepted", "reason": "future_reason"},
            ),
            (
                "remediation_reconciliation_attempt.future.durable_dispatching",
                {"result": "future", "reason": "durable_dispatching"},
            ),
            (
                "remediation_reconciliation_future.accepted.durable_dispatching",
                {"result": "accepted", "reason": "durable_dispatching"},
            ),
        ):
            with self.subTest(event_type=event_type):
                self.assertEqual(reconciliation_timeline_payload(event_type, payload), {})

    def test_event_name_and_payload_must_agree(self) -> None:
        self.assertEqual(
            reconciliation_timeline_payload(
                "remediation_reconciliation_attempt.accepted.durable_dispatching",
                {"result": "unknown", "reason": "durable_dispatching"},
            ),
            {},
        )
        self.assertEqual(
            reconciliation_timeline_payload(
                "remediation_reconciliation_recovered.accepted.durable_dispatching",
                {"result": "accepted", "reason": "legacy_unknown"},
            ),
            {},
        )

    def test_noncanonical_event_names_fail_closed(self) -> None:
        payload = {"result": "accepted", "reason": "durable_dispatching"}
        for event_type in (
            "remediation_reconciliation_attempt.accepted.durable_dispatching.extra",
            "remediation_reconciliation_attempt.accepted",
            "remediation_reconciliation_.accepted.durable_dispatching",
            "remediation_reconciliation_attempt..durable_dispatching",
        ):
            with self.subTest(event_type=event_type):
                self.assertEqual(reconciliation_timeline_payload(event_type, payload), {})


if __name__ == "__main__":
    unittest.main()
