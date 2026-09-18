import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
spec = importlib.util.spec_from_file_location("stageguard_validation_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(runner)


class TelemetrySimulatorValidationOwnershipTests(unittest.TestCase):
    def test_simulator_has_explicit_exact_filename_gate(self):
        gates = {gate.name: gate for gate in runner.GATES}
        self.assertIn("telemetry simulator", gates)
        gate = gates["telemetry simulator"]
        self.assertEqual(gate.patterns, ("test_simulator.py",))
        self.assertFalse(any("*" in pattern or "?" in pattern for pattern in gate.patterns))

    def test_simulator_is_owned_before_evidence_consumers(self):
        names = [gate.name for gate in runner.GATES]
        self.assertLess(names.index("telemetry simulator"), names.index("evidence and diagnosis"))
        selections = tuple((gate, runner._files(gate)) for gate in runner.GATES)
        owners = [gate.name for gate, files in selections if any(path.name == "test_simulator.py" for path in files)]
        self.assertEqual(owners, ["telemetry simulator"])


if __name__ == "__main__":
    unittest.main()
