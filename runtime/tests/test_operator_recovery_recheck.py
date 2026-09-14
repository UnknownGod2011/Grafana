import unittest

from operator_console import CONSOLE_HTML, CONSOLE_JS


class OperatorRecoveryRecheckTests(unittest.TestCase):
    def test_console_exposes_explicit_no_replay_recovery_recheck(self):
        self.assertIn('id="recheck-recovery"', CONSOLE_HTML)
        self.assertIn('id="recheck-state"', CONSOLE_HTML)
        self.assertIn("Recovery recheck reads fresh Grafana telemetry only", CONSOLE_HTML)
        self.assertIn("const recoveryRecheckAvailable=()", CONSOLE_JS)
        self.assertIn("current?.outcome?.status==='recovery_unverified'", CONSOLE_JS)
        self.assertIn("current?.outcome?.action_result?.accepted===true", CONSOLE_JS)
        self.assertIn("q('recheck-recovery').disabled=!canRecheck", CONSOLE_JS)
        self.assertIn("/v1/recovery/recheck", CONSOLE_JS)
        self.assertIn("The remediation provider will NOT be called again", CONSOLE_JS)
        self.assertIn("without replaying remediation", CONSOLE_JS)

    def test_recheck_remains_behind_existing_composite_safety_interlocks(self):
        self.assertIn("const canRecheck=recoveryRecheckAvailable()&&!blocked()", CONSOLE_JS)
        self.assertIn("if(blocked()||!recoveryRecheckAvailable())return", CONSOLE_JS)
        self.assertNotIn("operation_id", CONSOLE_JS)
        self.assertNotIn("provider_url", CONSOLE_JS)
        self.assertNotIn("localStorage", CONSOLE_JS)
        self.assertNotIn("sessionStorage", CONSOLE_JS)


if __name__ == "__main__":
    unittest.main()
