import unittest

from operator_console import CONSOLE_HTML, CONSOLE_JS


class OperatorIntegrityPolicyTests(unittest.TestCase):
    def test_console_surfaces_bounded_integrity_policy(self):
        self.assertIn('id="integrity-safety"', CONSOLE_HTML)
        self.assertIn('id="integrity-title"', CONSOLE_HTML)
        self.assertIn('id="integrity-state"', CONSOLE_HTML)
        self.assertIn("data.audit_integrity", CONSOLE_JS)
        self.assertIn("data.audit_integrity_policy", CONSOLE_JS)
        for state in ("disabled", "unbound_legacy", "verified", "failed"):
            self.assertIn(state, CONSOLE_JS)
        for policy in ("allow_unbound_legacy", "require_verified"):
            self.assertIn(policy, CONSOLE_JS)

    def test_hardened_policy_is_a_lifecycle_block(self):
        self.assertIn("auditIntegrityPolicy==='require_verified'&&auditIntegrity!=='verified'", CONSOLE_JS)
        self.assertIn("const lifecycleBlocked=()=>checkpointState==='conflicted'||checkpointState==='execution_uncertain'||auditPolicyBlocked()", CONSOLE_JS)
        self.assertIn("q('investigate').disabled=lifecycleBlocked()", CONSOLE_JS)
        self.assertIn("q('approval-revision').disabled=lifecycleBlocked()||!current", CONSOLE_JS)
        self.assertIn("q('execute').disabled=lifecycleBlocked()||!approval", CONSOLE_JS)

    def test_legacy_hardened_guidance_never_suggests_bypass(self):
        self.assertIn("legitimate lifecycle write must establish authenticated v3 state", CONSOLE_JS)
        self.assertIn("do not bypass the policy or edit checkpoint files manually", CONSOLE_JS)
        self.assertIn("fresh Grafana evidence", CONSOLE_JS)
        self.assertNotIn("operation_id", CONSOLE_JS)
        self.assertNotIn("provider_url", CONSOLE_JS)
        self.assertNotIn("localStorage", CONSOLE_JS)
        self.assertNotIn("sessionStorage", CONSOLE_JS)

    def test_invalid_server_values_fail_hardened(self):
        self.assertIn("safeAuditIntegrity", CONSOLE_JS)
        self.assertIn("?'failed'", CONSOLE_JS)
        self.assertIn("safeAuditPolicy", CONSOLE_JS)
        self.assertIn("?'require_verified'", CONSOLE_JS)


if __name__ == "__main__":
    unittest.main()
