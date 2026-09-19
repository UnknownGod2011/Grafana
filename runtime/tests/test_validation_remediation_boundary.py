"""Contract for the consolidated validator's mutation-capable remediation boundary."""
from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_stageguard_validation.py"
spec = importlib.util.spec_from_file_location("stageguard_validation_remediation_contract", SCRIPT)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec); sys.modules[spec.name] = validator; spec.loader.exec_module(validator)
sys.path.insert(0, str(ROOT / "runtime"))
from production_remediation import AllowlistedProductionRemediationClient


class HostileIdentity:
    """Caller-controlled object that must never reach equality comparison."""
    def __eq__(self, _other):
        raise AssertionError("hostile target identity reached equality comparison")


class RecordingTransport:
    def __init__(self):
        self.requests = []

    def execute(self, request, *, timeout_seconds):
        self.requests.append((request, timeout_seconds))
        raise AssertionError("invalid target reached remediation transport")


class RemediationValidationBoundaryTests(unittest.TestCase):
    def test_remediation_gate_owns_transport_provider_receiver_and_result_contracts(self):
        gates = {gate.name: gate for gate in validator.GATES}
        self.assertIn("remediation adapter boundary", gates)
        names = {p.name for p in validator._files(gates["remediation adapter boundary"])}
        required = {"test_remediation_receiver.py", "test_remediation_result_boundary.py", "test_production_remediation.py", "test_http_remediation_transport.py", "test_http_remediation_tls_integration.py"}
        self.assertTrue(required <= names, f"missing remediation safety contracts: {sorted(required - names)}")

    def test_remediation_boundary_precedes_execution_and_mcp(self):
        order = [gate.name for gate in validator.GATES]; remediation = order.index("remediation adapter boundary")
        self.assertLess(remediation, order.index("execution safety")); self.assertLess(remediation, order.index("Grafana MCP"))

    def test_local_uncertainty_barrier_is_not_omitted(self):
        execution = next(g for g in validator.GATES if g.name == "execution safety")
        self.assertIn("test_local_execution_uncertainty_barrier.py", {p.name for p in validator._files(execution)})

    def test_runtime_targets_reject_hostile_objects_before_comparison_or_transport(self):
        operation_id = "sg-" + "a" * 40
        for production_id, uplink in (
            (HostileIdentity(), "uplink-b"),
            ("broadcast-alpha", HostileIdentity()),
        ):
            with self.subTest(production_id=type(production_id).__name__, uplink=type(uplink).__name__):
                transport = RecordingTransport()
                client = AllowlistedProductionRemediationClient(
                    transport,
                    allowed_production_id="broadcast-alpha",
                    allowed_uplink="uplink-b",
                    sleep=lambda _: None,
                )
                result = client.recover_uplink_idempotent(production_id, uplink, operation_id)
                self.assertFalse(result.accepted)
                self.assertEqual("unsupported remediation target", result.detail)
                self.assertEqual(0, result.metadata["attempt_count"])
                self.assertEqual(operation_id, result.metadata["operation_id"])
                self.assertEqual([], transport.requests)

    def test_runtime_targets_reject_noncanonical_strings_before_transport(self):
        operation_id = "sg-" + "b" * 40
        invalid_targets = ("", " broadcast-alpha", "broadcast-alpha ", "broadcast\nalpha", "x" * 129)
        for field in ("production_id", "uplink"):
            for invalid in invalid_targets:
                with self.subTest(field=field, invalid=repr(invalid)):
                    transport = RecordingTransport()
                    client = AllowlistedProductionRemediationClient(
                        transport,
                        allowed_production_id="broadcast-alpha",
                        allowed_uplink="uplink-b",
                        sleep=lambda _: None,
                    )
                    production_id = invalid if field == "production_id" else "broadcast-alpha"
                    uplink = invalid if field == "uplink" else "uplink-b"
                    result = client.recover_uplink_idempotent(production_id, uplink, operation_id)
                    self.assertFalse(result.accepted)
                    self.assertEqual("unsupported remediation target", result.detail)
                    self.assertEqual(0, result.metadata["attempt_count"])
                    self.assertEqual(operation_id, result.metadata["operation_id"])
                    self.assertEqual([], transport.requests)

if __name__ == "__main__": unittest.main()
