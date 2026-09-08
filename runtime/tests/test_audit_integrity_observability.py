import unittest
from unittest.mock import patch

from api import (
    _AUDIT_INTEGRITY_STATES,
    _audit_integrity_state,
    _lifecycle_view,
    _service_metrics,
    _service_readiness,
)


class ReadyResult:
    def to_dict(self):
        return {"ready": True, "checks": {"prometheus_mcp": "ok", "loki_mcp": "ok"}}


class ReadyProbe:
    def check(self):
        return ReadyResult()

    def prometheus_metrics(self):
        return ""


class ObservableService:
    _checkpoint_store = None

    def __init__(self, integrity="verified", checkpoint_state="synchronized"):
        self.integrity = integrity
        self.state = checkpoint_state

    def checkpoint_state(self):
        return self.state

    def audit_integrity_state(self):
        return self.integrity

    def status(self):
        return None


class AuditIntegrityObservabilityTests(unittest.TestCase):
    def test_lifecycle_view_exposes_bounded_integrity_state(self):
        for state in _AUDIT_INTEGRITY_STATES:
            with self.subTest(state=state):
                view = _lifecycle_view(ObservableService(state))
                self.assertEqual(state, view["audit_integrity"])
                self.assertIsNone(view["incident"])

    def test_failed_integrity_blocks_readiness_independently_of_checkpoint_state(self):
        service = ObservableService("failed", checkpoint_state="synchronized")
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            readiness = _service_readiness(service)

        self.assertFalse(readiness["ready"])
        self.assertEqual("synchronized", readiness["checks"]["checkpoint"])
        self.assertEqual("failed", readiness["checks"]["audit_integrity"])

    def test_nonfailed_integrity_does_not_override_healthy_evidence_plane(self):
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            for state in ("disabled", "unbound_legacy", "verified"):
                with self.subTest(state=state):
                    readiness = _service_readiness(ObservableService(state))
                    self.assertTrue(readiness["ready"])
                    self.assertEqual(state, readiness["checks"]["audit_integrity"])

    def test_metric_is_one_hot_and_fixed_cardinality(self):
        service = ObservableService("verified")
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            metrics = _service_metrics(service)

        lines = [line for line in metrics.splitlines() if line.startswith("stageguard_audit_integrity{")]
        self.assertEqual(len(_AUDIT_INTEGRITY_STATES), len(lines))
        self.assertEqual(1, sum(line.endswith(" 1") for line in lines))
        self.assertIn('stageguard_audit_integrity{state="verified"} 1', lines)

        for forbidden in (
            "incident-001",
            "operation-2b3402",
            "broadcast-alpha",
            "https://provider.example/remediate",
            "secret-token",
        ):
            self.assertNotIn(forbidden, metrics)

    def test_invalid_or_failing_integrity_state_collapses_to_failed(self):
        invalid = ObservableService("provider-operation-id-should-not-be-a-label")
        self.assertEqual("failed", _audit_integrity_state(invalid))

        class FailingService(ObservableService):
            def audit_integrity_state(self):
                raise RuntimeError("secret provider detail")

        self.assertEqual("failed", _audit_integrity_state(FailingService()))

        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            readiness = _service_readiness(invalid)
            metrics = _service_metrics(invalid)

        self.assertFalse(readiness["ready"])
        self.assertEqual("failed", readiness["checks"]["audit_integrity"])
        self.assertIn('stageguard_audit_integrity{state="failed"} 1', metrics)
        self.assertNotIn("provider-operation-id-should-not-be-a-label", metrics)

    def test_missing_integrity_getter_is_explicitly_disabled_for_legacy_service_stubs(self):
        class LegacyService:
            _checkpoint_store = None

            def checkpoint_state(self):
                return "disabled"

            def status(self):
                return None

        self.assertEqual("disabled", _audit_integrity_state(LegacyService()))


if __name__ == "__main__":
    unittest.main()
