from pathlib import Path
import json
import tempfile
import unittest

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from audit_anchor import DEFAULT_ANCHOR_INTERVAL, MAX_VERIFICATION_SUFFIX_EVENTS
from bootstrap import build_runtime
from execution_safety import ExecutionSafeIncidentService
from remediation import ActionResult


class FakeMetrics:
    datasource_uid = "prom-main"

    def __init__(self, values=None):
        self.closed = False
        self.values = None if values is None else list(values)
        self.index = 0

    def instant(self, _promql):
        if self.values is None:
            return 1.0
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value

    def close(self):
        self.closed = True


class CountingRemediation:
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


def diagnosed_with_recovery():
    # Six investigation samples followed by two consecutive healthy recovery samples.
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]


class BootstrapExecutionSafetyTests(unittest.TestCase):
    def _bundle(self, root: Path, **kwargs):
        example = Path(__file__).parents[1] / "telemetry.example.json"
        return build_runtime(
            telemetry_config=example,
            activation_path=None,
            audit_path=root / "audit.jsonl",
            host="127.0.0.1",
            port=0,
            checkpoint_backend="none",
            metrics_factory=FakeMetrics,
            **kwargs,
        )

    def test_runtime_composes_anchor_and_execution_safety_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle(Path(tmp))
            try:
                self.assertIsInstance(bundle.service, AnchoredExecutionSafeIncidentService)
                self.assertIsInstance(bundle.service, ExecutionSafeIncidentService)
                self.assertIsInstance(bundle.service._audit, AnchoredJsonlAuditLog)
                self.assertEqual("synchronized", bundle.service.checkpoint_state())
                self.assertEqual("clear", bundle.service.execution_reconciliation_state())
                self.assertEqual(DEFAULT_ANCHOR_INTERVAL, bundle.service.audit_anchor_state()["interval"])
            finally:
                bundle.close()

    def test_runtime_accepts_bounded_anchor_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle(Path(tmp), audit_anchor_interval=17)
            try:
                self.assertEqual(17, bundle.service.audit_anchor_state()["interval"])
            finally:
                bundle.close()

    def test_runtime_rejects_anchor_interval_outside_verification_bound(self):
        for value in (0, MAX_VERIFICATION_SUFFIX_EVENTS + 1, True):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, "audit anchor interval"):
                    self._bundle(Path(tmp), audit_anchor_interval=value)

    def test_default_build_runtime_restarts_verified_after_physical_anchor_compaction_without_remediation_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = Path(__file__).parents[1] / "telemetry.example.json"
            audit_path = root / "audit.jsonl"
            checkpoint_path = root / "checkpoint.json"
            first_remediation = CountingRemediation()

            first = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=audit_path,
                host="127.0.0.1",
                port=0,
                checkpoint_backend="json",
                checkpoint_path=checkpoint_path,
                audit_anchor_interval=1,
                metrics_factory=lambda: FakeMetrics(diagnosed_with_recovery()),
                remediation_factory=lambda _profile: first_remediation,
            )
            try:
                investigated = first.service.investigate(actor="bootstrap-test")
                first.service.approve(
                    incident_id=investigated.incident_id,
                    revision=investigated.revision,
                    approved_by="bootstrap-test-operator",
                )
                completed = first.service.execute_approved(actor="bootstrap-test")
                self.assertIsNotNone(completed.outcome)
                self.assertEqual("recovered", completed.outcome.status)
                self.assertEqual(1, first_remediation.calls)
                self.assertEqual("verified", first.service.audit_integrity_state())
                anchor_sequence = first.service.audit_anchor_state()["sequence"]
                self.assertGreater(anchor_sequence, 0)
            finally:
                first.close()

            retained_lines = []
            for line in audit_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                if int(json.loads(line)["sequence"]) > anchor_sequence:
                    retained_lines.append(line)
            audit_path.write_text(
                "" if not retained_lines else "\n".join(retained_lines) + "\n",
                encoding="utf-8",
            )

            restarted_remediation = CountingRemediation()
            restarted = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=audit_path,
                host="127.0.0.1",
                port=0,
                checkpoint_backend="json",
                checkpoint_path=checkpoint_path,
                audit_anchor_interval=1,
                metrics_factory=lambda: FakeMetrics([]),
                remediation_factory=lambda _profile: restarted_remediation,
            )
            try:
                restored = restarted.service.status()
                self.assertIsNotNone(restored)
                self.assertEqual("verified", restarted.service.audit_integrity_state())
                self.assertEqual("synchronized", restarted.service.checkpoint_state())
                self.assertEqual("clear", restarted.service.execution_reconciliation_state())
                self.assertIsNotNone(restored.approval)
                self.assertIsNotNone(restored.outcome)
                self.assertEqual("recovered", restored.outcome.status)
                self.assertEqual(0, restarted_remediation.calls)
                with self.assertRaisesRegex(RuntimeError, "already been consumed"):
                    restarted.service.execute_approved(actor="bootstrap-test")
                self.assertEqual(0, restarted_remediation.calls)
            finally:
                restarted.close()


if __name__ == "__main__":
    unittest.main()
