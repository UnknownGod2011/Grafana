import unittest

from operator_console import CONSOLE_HTML, CONSOLE_JS


class OperatorRecoveryRecheckTests(unittest.TestCase):
    def test_console_uses_server_derived_no_replay_recovery_contract(self):
        self.assertIn('id="recheck-recovery"', CONSOLE_HTML)
        self.assertIn('id="recheck-state"', CONSOLE_HTML)
        self.assertIn("Recovery recheck reads fresh Grafana telemetry only", CONSOLE_HTML)
        self.assertIn("const safeRecoveryView=v=>", CONSOLE_JS)
        self.assertIn("const recoveryRecheckAvailable=()=>recoveryContractValid&&recoveryView?.recheck_eligible===true", CONSOLE_JS)
        self.assertIn("render(data.incident,data.recovery", CONSOLE_JS)
        self.assertNotIn("current?.outcome?.status==='recovery_unverified'", CONSOLE_JS)
        self.assertNotIn("current?.outcome?.action_result?.accepted===true", CONSOLE_JS)
        self.assertIn("q('recheck-recovery').disabled=!canRecheck", CONSOLE_JS)
        self.assertIn("/v1/recovery/recheck", CONSOLE_JS)
        self.assertIn("The remediation provider will NOT be called again", CONSOLE_JS)
        self.assertIn("without replaying remediation", CONSOLE_JS)

    def test_recovery_contract_is_strict_and_fails_closed(self):
        self.assertIn("typeof v.action_accepted!=='boolean'", CONSOLE_JS)
        self.assertIn("typeof v.recheck_eligible!=='boolean'", CONSOLE_JS)
        self.assertIn("typeof v.verified!=='boolean'", CONSOLE_JS)
        self.assertIn("!Number.isInteger(v.sample_count)", CONSOLE_JS)
        self.assertIn("v.sample_count>100", CONSOLE_JS)
        self.assertIn("typeof v.checkpoint_phase_consistent!=='boolean'", CONSOLE_JS)
        self.assertIn("v.verified!==expectedVerified", CONSOLE_JS)
        self.assertIn("v.recheck_eligible!==expectedRecheck", CONSOLE_JS)
        self.assertIn("const recoveryContractBlocked=()=>!recoveryContractValid||recoveryView?.checkpoint_phase_consistent!==true", CONSOLE_JS)
        self.assertIn("Recovery contract unavailable or inconsistent", CONSOLE_JS)
        self.assertIn("StageGuard keeps all lifecycle mutations blocked rather than inferring recovery state in the browser.", CONSOLE_JS)

    def test_cold_restart_recovery_unverified_is_recheck_only_and_recovered_is_terminal(self):
        self.assertIn("recoveryView.state==='recovery_unverified'?'RECHECK ONLY'", CONSOLE_JS)
        self.assertIn("recoveryView.state==='recovered'?'RECOVERED ✓'", CONSOLE_JS)
        self.assertIn("recoveryView.state==='recovery_unverified'?'Recheck available · no provider replay'", CONSOLE_JS)
        self.assertIn("recoveryView.state==='recovered'?'Verified by Grafana'", CONSOLE_JS)
        self.assertIn("q('execute').disabled=blocked()||diagnosisUnavailable()||!approval||!!current.outcome", CONSOLE_JS)
        self.assertIn("q('recovery').textContent=recoveryContractValid?JSON.stringify(recoveryView,null,2):''", CONSOLE_JS)
        self.assertNotIn("JSON.stringify(current.outcome,null,2)", CONSOLE_JS)

    def test_recheck_remains_behind_existing_composite_safety_interlocks(self):
        self.assertIn("const canRecheck=recoveryRecheckAvailable()&&!blocked()", CONSOLE_JS)
        self.assertIn("if(blocked()||!recoveryRecheckAvailable())return", CONSOLE_JS)
        self.assertNotIn("operation_id", CONSOLE_JS)
        self.assertNotIn("provider_url", CONSOLE_JS)
        self.assertNotIn("localStorage", CONSOLE_JS)
        self.assertNotIn("sessionStorage", CONSOLE_JS)


if __name__ == "__main__":
    unittest.main()
