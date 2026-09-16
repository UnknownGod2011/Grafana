#!/usr/bin/env python3
from __future__ import annotations

import math
import unittest

from runtime.timeline_projection import reconciliation_timeline_payload, timeline_payload


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


class TimelinePayloadScalarTests(unittest.TestCase):
    def test_allowlisted_static_fields_project_only_safe_json_scalars(self) -> None:
        static_fields = {"incident_opened": ("severity", "attempt", "details")}
        payload = {
            "severity": "high",
            "attempt": 3,
            "details": True,
            "provider_body": {"secret": "must-not-leak"},
            "operation_id": "must-not-leak",
        }
        self.assertEqual(
            timeline_payload("incident_opened", payload, static_fields),
            {"severity": "high", "attempt": 3, "details": True},
        )

    def test_nested_objects_and_arrays_are_rejected_even_when_allowlisted(self) -> None:
        static_fields = {"incident_opened": ("nested", "items")}
        self.assertEqual(
            timeline_payload(
                "incident_opened",
                {"nested": {"secret": "x"}, "items": ["x"]},
                static_fields,
            ),
            {},
        )

    def test_oversized_strings_and_arbitrary_precision_integers_are_rejected(self) -> None:
        static_fields = {"incident_opened": ("message", "counter")}
        self.assertEqual(
            timeline_payload(
                "incident_opened",
                {"message": "x" * 513, "counter": 1 << 63},
                static_fields,
            ),
            {},
        )

    def test_non_finite_floats_are_rejected_but_finite_floats_are_allowed(self) -> None:
        static_fields = {"incident_opened": ("good", "bad")}
        self.assertEqual(
            timeline_payload(
                "incident_opened",
                {"good": 1.25, "bad": math.inf},
                static_fields,
            ),
            {"good": 1.25},
        )

    def test_unknown_event_types_delegate_only_to_canonical_reconciliation_projection(self) -> None:
        self.assertEqual(
            timeline_payload(
                "remediation_reconciliation_attempt.accepted.durable_dispatching",
                {"result": "accepted", "reason": "durable_dispatching", "body": {"secret": "x"}},
                {},
            ),
            {"result": "accepted", "reason": "durable_dispatching"},
        )
        self.assertEqual(
            timeline_payload("future_event", {"message": "should not leak"}, {}),
            {},
        )


if __name__ == "__main__":
    unittest.main()
