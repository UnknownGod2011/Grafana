from __future__ import annotations

import sys
import unittest
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from cloud_run_metrics_bridge import validate_stageguard_metrics  # noqa: E402


METRIC = b"stageguard_remediation_execution_deadline_exceeded"


class CloudRunMetricsSentinelFamilyTests(unittest.TestCase):
    def test_accepts_exactly_one_label_free_boolean_sentinel(self) -> None:
        for value in (b"0", b"1"):
            with self.subTest(value=value):
                validate_stageguard_metrics(METRIC + b" " + value + b"\n")

    def test_rejects_valid_bare_sentinel_plus_labeled_family_series(self) -> None:
        for labeled_value in (b"0", b"1"):
            payload = (
                METRIC
                + b" 0\n"
                + METRIC
                + b'{source="spoofed"} '
                + labeled_value
                + b"\n"
            )
            with self.subTest(labeled_value=labeled_value):
                with self.assertRaisesRegex(RuntimeError, "unauthorized labels"):
                    validate_stageguard_metrics(payload)

    def test_rejects_labeled_series_before_valid_bare_sentinel(self) -> None:
        payload = METRIC + b'{source="shadow"} 0\n' + METRIC + b" 0\n"
        with self.assertRaisesRegex(RuntimeError, "unauthorized labels"):
            validate_stageguard_metrics(payload)

    def test_similarly_prefixed_metric_is_not_treated_as_sentinel_family(self) -> None:
        payload = (
            METRIC
            + b"_total 99\n"
            + METRIC
            + b" 0\n"
        )
        validate_stageguard_metrics(payload)

    def test_label_brace_without_valid_bare_sentinel_fails_closed(self) -> None:
        payload = METRIC + b'{source="only-labeled"} 0\n'
        with self.assertRaisesRegex(RuntimeError, "unauthorized labels"):
            validate_stageguard_metrics(payload)


if __name__ == "__main__":
    unittest.main()
