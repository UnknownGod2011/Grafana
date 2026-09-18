from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("stageguard_validation_runner_restart", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RestartRecoveryValidationOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.runner = load_runner()
        self.gates = {gate.name: gate for gate in self.runner.GATES}

    def test_restart_recovery_contracts_have_explicit_safe_owners(self):
        lifecycle = self.gates["incident lifecycle"].patterns
        execution = self.gates["execution safety"].patterns
        self.assertIn("test_recovery_recheck_restart.py", lifecycle)
        self.assertIn("test_transition_failure_snapshot_authority.py", lifecycle)
        self.assertIn("test_subprocess_crash_recovery.py", execution)

    def test_new_contracts_are_not_admitted_by_new_broad_wildcards(self):
        lifecycle = self.gates["incident lifecycle"].patterns
        execution = self.gates["execution safety"].patterns
        self.assertNotIn("test_*restart*.py", lifecycle)
        self.assertNotIn("test_*transition_failure*.py", lifecycle)
        self.assertFalse(any("*crash*" in pattern for pattern in execution))

    def test_classified_files_are_owned(self):
        selections = tuple((gate, self.runner._files(gate)) for gate in self.runner.GATES)
        owners = {}
        for gate, files in selections:
            for path in files:
                owners.setdefault(path.name, []).append(gate.name)
        for name in (
            "test_recovery_recheck_restart.py",
            "test_transition_failure_snapshot_authority.py",
            "test_subprocess_crash_recovery.py",
        ):
            self.assertIn(name, owners)


if __name__ == "__main__":
    unittest.main()
