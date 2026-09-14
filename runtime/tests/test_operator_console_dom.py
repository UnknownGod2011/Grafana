import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from operator_console import CONSOLE_HTML, CONSOLE_JS


NODE = shutil.which("node")


class OperatorConsoleDomTests(unittest.TestCase):
    """Execute the real embedded cockpit JavaScript against a tiny DOM.

    This intentionally uses only Node's standard runtime. It gives us behavioral
    coverage of the safety controls without adding Playwright/jsdom or requiring
    Grafana, Gemini, a remediation provider, or browser credentials.
    """

    maxDiff = None

    def _run_console(self, recovery):
        if NODE is None:
            self.skipTest("node is not installed; DOM harness requires a JavaScript runtime")

        incident = {
            "incident_id": "incident-dom-001",
            "revision": "rev-dom-001",
            "status": "active",
            "production_id": "prod-a",
            "feed": "uplink-a",
            "report": {
                "status": "diagnosed",
                "summary": "Synthetic DOM harness incident",
                "hypothesis": "uplink degradation",
                "confidence": 0.97,
                "evidence": [],
                "unavailable_evidence": [],
            },
            "approval": None,
            "outcome": None,
            "briefing": None,
        }
        if isinstance(recovery, dict) and recovery.get("state") in {"recovery_unverified", "recovered"}:
            incident["outcome"] = {
                "status": recovery["state"],
                "action_result": {"accepted": True},
                "recovery_samples": [],
            }

        lifecycle = {
            "incident": incident,
            "recovery": recovery,
            "checkpoint_state": "synchronized",
            "execution_reconciliation_state": "clear",
            "execution_reconciliation_reason": "clear",
            "audit_integrity": "disabled",
            "audit_integrity_policy": "allow_unbound_legacy",
            "safety_state": "ok",
            "execution_reconciliation_reference": None,
        }

        ids = []
        marker = 'id="'
        for fragment in CONSOLE_HTML.split(marker)[1:]:
            value = fragment.split('"', 1)[0]
            if value not in ids:
                ids.append(value)

        harness = textwrap.dedent(
            f"""
            const vm = require('vm');
            const source = {json.dumps(CONSOLE_JS)};
            const lifecycle = {json.dumps(lifecycle)};
            const ids = {json.dumps(ids)};

            class Element {{
              constructor(id='') {{
                this.id=id; this.hidden=false; this.disabled=false; this.textContent='';
                this.value=''; this.children=[]; this.listeners={{}}; this.dataset={{}};
              }}
              addEventListener(type, fn) {{ (this.listeners[type] ||= []).push(fn); }}
              appendChild(child) {{ this.children.push(child); return child; }}
              replaceChildren(...children) {{ this.children=[...children]; }}
              setAttribute() {{}}
              removeAttribute() {{}}
              focus() {{}}
              async click() {{
                for (const fn of (this.listeners.click || [])) await fn({{target:this, preventDefault(){{}}}});
              }}
            }}

            const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
            const document = {{
              readyState: 'complete',
              getElementById(id) {{ return elements[id] || (elements[id] = new Element(id)); }},
              createElement() {{ return new Element(); }},
              addEventListener(type, fn) {{ if (type === 'DOMContentLoaded') fn(); }},
            }};
            global.document = document;
            global.window = global;
            global.confirm = () => true;
            global.fetch = async () => ({{
              ok: true,
              status: 200,
              json: async () => lifecycle,
            }});

            process.on('unhandledRejection', error => {{ throw error; }});
            vm.runInThisContext(source, {{filename:'operator.js'}});

            setTimeout(() => {{
              const out = {{
                investigateDisabled: elements.investigate.disabled,
                briefingDisabled: elements.briefing.disabled,
                approveDisabled: elements.approve.disabled,
                executeDisabled: elements.execute.disabled,
                recheckDisabled: elements['recheck-recovery'].disabled,
                judgeRecovery: elements['judge-recovery'].textContent,
                recoveryCardHidden: elements['recovery-card'].hidden,
                recoveryText: elements.recovery.textContent,
                lifecycleSafetyHidden: elements['lifecycle-recovery'].hidden,
                lifecycleSafetyMessage: elements['lifecycle-recovery-message'].textContent,
              }};
              process.stdout.write(JSON.stringify(out));
            }}, 40);
            """
        )

        with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as handle:
            handle.write(harness)
            script_path = handle.name
        try:
            proc = subprocess.run(
                [NODE, script_path],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        finally:
            try:
                import os
                os.unlink(script_path)
            except OSError:
                pass

        if proc.returncode != 0:
            self.fail(f"operator DOM harness failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"operator DOM harness returned invalid JSON: {proc.stdout!r}\n{proc.stderr}\n{exc}")

    def test_recovery_unverified_is_recheck_only(self):
        state = self._run_console({
            "state": "recovery_unverified",
            "action_accepted": True,
            "recheck_eligible": True,
            "verified": False,
            "sample_count": 6,
            "checkpoint_phase_consistent": True,
        })
        self.assertFalse(state["recheckDisabled"])
        self.assertTrue(state["executeDisabled"])
        self.assertEqual("RECHECK ONLY", state["judgeRecovery"])
        self.assertFalse(state["recoveryCardHidden"])
        self.assertIn('"state": "recovery_unverified"', state["recoveryText"])
        self.assertTrue(state["lifecycleSafetyHidden"])

    def test_recovered_is_terminal(self):
        state = self._run_console({
            "state": "recovered",
            "action_accepted": True,
            "recheck_eligible": False,
            "verified": True,
            "sample_count": 2,
            "checkpoint_phase_consistent": True,
        })
        self.assertTrue(state["recheckDisabled"])
        self.assertTrue(state["executeDisabled"])
        self.assertEqual("RECOVERED ✓", state["judgeRecovery"])
        self.assertFalse(state["recoveryCardHidden"])
        self.assertIn('"verified": true', state["recoveryText"])
        self.assertTrue(state["lifecycleSafetyHidden"])

    def test_malformed_recovery_contract_fails_closed(self):
        state = self._run_console({
            "state": "recovery_unverified",
            "action_accepted": True,
            "recheck_eligible": "yes",
            "verified": False,
            "sample_count": 6,
            "checkpoint_phase_consistent": True,
        })
        self.assertTrue(state["investigateDisabled"])
        self.assertTrue(state["briefingDisabled"])
        self.assertTrue(state["approveDisabled"])
        self.assertTrue(state["executeDisabled"])
        self.assertTrue(state["recheckDisabled"])
        self.assertFalse(state["lifecycleSafetyHidden"])
        self.assertIn("Recovery contract unavailable or inconsistent", state["lifecycleSafetyMessage"])

    def test_checkpoint_inconsistent_recovery_contract_fails_closed(self):
        state = self._run_console({
            "state": "recovery_unverified",
            "action_accepted": True,
            "recheck_eligible": True,
            "verified": False,
            "sample_count": 6,
            "checkpoint_phase_consistent": False,
        })
        self.assertTrue(state["recheckDisabled"])
        self.assertTrue(state["executeDisabled"])
        self.assertFalse(state["lifecycleSafetyHidden"])


if __name__ == "__main__":
    unittest.main()
