#!/usr/bin/env python3
from __future__ import annotations

import math
import unittest
from collections.abc import Mapping

from runtime.timeline_projection import reconciliation_timeline_payload, timeline_payload


class BrokenMapping(Mapping):
    """Mapping whose reads fail like a malformed persistence/plugin adapter."""
    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __getitem__(self, key):
        raise RuntimeError("malformed mapping")

    def get(self, key, default=None):
        raise RuntimeError("malformed mapping")


class ReconciliationTimelineProjectionTests(unittest.TestCase):
    def test_projects_only_bounded_result_and_reason(self) -> None:
        projected = reconciliation_timeline_payload(
            "remediation_reconciliation_attempt.accepted.durable_dispatching",
            {"result": "accepted", "reason": "durable_dispatching", "operation_id": "secret", "provider_body": {"token": "secret"}},
        )
        self.assertEqual(projected, {"result": "accepted", "reason": "durable_dispatching"})

    def test_supports_all_current_bounded_states(self) -> None:
        for stage in ("attempt", "recovered"):
            for result in ("accepted", "not_found", "unknown"):
                for reason in ("durable_dispatching", "legacy_unknown", "post_dispatch_checkpoint_regression", "phase_unavailable"):
                    with self.subTest(stage=stage, result=result, reason=reason):
                        self.assertEqual(reconciliation_timeline_payload(f"remediation_reconciliation_{stage}.{result}.{reason}", {"result": result, "reason": reason}), {"result": result, "reason": reason})

    def test_non_reconciliation_event_fails_closed(self) -> None:
        self.assertEqual(reconciliation_timeline_payload("remediation_completed", {"result": "accepted", "reason": "durable_dispatching"}), {})

    def test_unbounded_or_future_values_fail_closed(self) -> None:
        for event_type, payload in (
            ("remediation_reconciliation_attempt.accepted.future_reason", {"result": "accepted", "reason": "future_reason"}),
            ("remediation_reconciliation_attempt.future.durable_dispatching", {"result": "future", "reason": "durable_dispatching"}),
            ("remediation_reconciliation_future.accepted.durable_dispatching", {"result": "accepted", "reason": "durable_dispatching"}),
        ):
            with self.subTest(event_type=event_type):
                self.assertEqual(reconciliation_timeline_payload(event_type, payload), {})

    def test_event_name_and_payload_must_agree(self) -> None:
        self.assertEqual(reconciliation_timeline_payload("remediation_reconciliation_attempt.accepted.durable_dispatching", {"result": "unknown", "reason": "durable_dispatching"}), {})

    def test_mapping_read_failures_fail_closed(self) -> None:
        self.assertEqual(reconciliation_timeline_payload("remediation_reconciliation_attempt.accepted.durable_dispatching", BrokenMapping()), {})


class TimelinePayloadScalarTests(unittest.TestCase):
    def test_allowlisted_static_fields_project_only_safe_json_scalars(self) -> None:
        static_fields = {"incident_opened": ("severity", "attempt", "details")}
        payload = {"severity": "high", "attempt": 3, "details": True, "provider_body": {"secret": "must-not-leak"}}
        self.assertEqual(timeline_payload("incident_opened", payload, static_fields), {"severity": "high", "attempt": 3, "details": True})

    def test_nested_objects_and_arrays_are_rejected_even_when_allowlisted(self) -> None:
        self.assertEqual(timeline_payload("incident_opened", {"nested": {"secret": "x"}, "items": ["x"]}, {"incident_opened": ("nested", "items")}), {})

    def test_oversized_strings_and_arbitrary_precision_integers_are_rejected(self) -> None:
        self.assertEqual(timeline_payload("incident_opened", {"message": "x" * 513, "counter": 1 << 63}, {"incident_opened": ("message", "counter")}), {})

    def test_terminal_dangerous_strings_are_rejected(self) -> None:
        for dangerous in ("line\nfeed", "carriage\rreturn", "tab\tvalue", "nul\x00value", "del\x7fvalue", "c1\x85next", "line\u2028separator", "para\u2029separator", "bidi\u202eoverride", "isolate\u2066text"):
            with self.subTest(dangerous=repr(dangerous)):
                self.assertEqual(timeline_payload("incident_opened", {"value": dangerous}, {"incident_opened": ("value",)}), {})

    def test_printable_unicode_and_scalar_boundaries_remain_allowed(self) -> None:
        value = "直播·ライブ·лайв·بث"
        self.assertEqual(timeline_payload("incident_opened", {"value": value, "minimum": -(1 << 63) + 1, "maximum": (1 << 63) - 1}, {"incident_opened": ("value", "minimum", "maximum")}), {"value": value, "minimum": -(1 << 63) + 1, "maximum": (1 << 63) - 1})

    def test_non_finite_floats_are_rejected_but_finite_floats_are_allowed(self) -> None:
        self.assertEqual(timeline_payload("incident_opened", {"good": 1.25, "bad": math.inf}, {"incident_opened": ("good", "bad")}), {"good": 1.25})

    def test_unknown_event_types_delegate_only_to_canonical_reconciliation_projection(self) -> None:
        self.assertEqual(timeline_payload("remediation_reconciliation_attempt.accepted.durable_dispatching", {"result": "accepted", "reason": "durable_dispatching"}, {}), {"result": "accepted", "reason": "durable_dispatching"})
        self.assertEqual(timeline_payload("future_event", {"message": "should not leak"}, {}), {})

    def test_static_policy_rejects_string_non_string_and_oversized_allowlists(self) -> None:
        for allowed in ("severity", ("severity", 7), tuple(f"field_{i}" for i in range(65))):
            self.assertEqual(timeline_payload("incident_opened", {"severity": "high"}, {"incident_opened": allowed}), {})

    def test_static_policy_rejects_unsafe_or_oversized_field_names(self) -> None:
        for field in ("", "line\nfeed", "c1\x85next", "line\u2028separator", "bidi\u202eoverride", "x" * 129):
            with self.subTest(field=repr(field)):
                self.assertEqual(timeline_payload("incident_opened", {field: "visible"}, {"incident_opened": (field,)}), {})

    def test_static_policy_accepts_printable_unicode_field_names_at_boundary(self) -> None:
        field = "測" * 128
        self.assertEqual(timeline_payload("incident_opened", {field: "visible"}, {"incident_opened": (field,)}), {field: "visible"})

    def test_static_policy_bounds_infinite_iterators(self) -> None:
        def forever():
            index = 0
            while True:
                yield f"field_{index}"
                index += 1
        self.assertEqual(timeline_payload("incident_opened", {"field_0": "visible"}, {"incident_opened": forever()}), {})

    def test_static_policy_rejects_iterator_failures(self) -> None:
        class BrokenIterator:
            def __iter__(self):
                raise RuntimeError("malformed policy")
        self.assertEqual(timeline_payload("incident_opened", {"severity": "high"}, {"incident_opened": BrokenIterator()}), {})

    def test_static_policy_mapping_lookup_failures_fail_closed(self) -> None:
        self.assertEqual(timeline_payload("incident_opened", {"severity": "high"}, BrokenMapping()), {})

    def test_payload_mapping_read_failures_fail_closed(self) -> None:
        self.assertEqual(timeline_payload("incident_opened", BrokenMapping(), {"incident_opened": ("severity",)}), {})

    def test_static_policy_accepts_exact_field_limit(self) -> None:
        allowed = tuple(f"field_{i}" for i in range(64))
        payload = {"field_0": "first", "field_63": "last"}
        self.assertEqual(timeline_payload("incident_opened", payload, {"incident_opened": allowed}), {"field_0": "first", "field_63": "last"})


if __name__ == "__main__":
    unittest.main()
