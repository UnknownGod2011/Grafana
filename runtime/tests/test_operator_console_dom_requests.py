import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from operator_console import CONSOLE_HTML, CONSOLE_JS


NODE = shutil.which("node")


class OperatorConsoleDomRequestTests(unittest.TestCase):
    """Behaviorally lock the cockpit's recovery-only network path.

    The test executes the real embedded JavaScript with Node's standard runtime,
    records every fetch call, clicks the real recovery-recheck control, and proves
    that the browser issues only the recovery verification mutation rather than
    replaying the remediation endpoint.
    """

    maxDiff = None

    def _run_recheck_click(self):
        if NODE is None:
            self.skipTest("node is not installed; DOM harness requires a JavaScript runtime")

        incident = {
            "incident_id": "incident-dom-request-001",
            "revision": "rev-dom-request-001",
            "status": "active",
            "production_id": "prod-a",
            "feed": "uplink-a",
            "report": {
                "status": "diagnosed",
                "summary": "Synthetic recovery-only request harness incident",
                "hypothesis": "uplink degradation",
                "confidence": 0.97,
                "evidence": [],
                "unavailable_evidence": [],
            },
            "approval": {
                "action": "failover",
                "target": "backup-uplink",
            },
            "outcome": {
                "status": "recovery_unverified",
                "action_result": {"accepted": True},
                "recovery_samples": [],
            },
            "briefing": None,
        }
        initial = {
            "incident": incident,
            "recovery": {
                "state": "recovery_unverified",
                "action_accepted": True,
                "recheck_eligible": True,
                "verified": False,
                "sample_count": 6,
                "checkpoint_phase_consistent": True,
            },
            "checkpoint_state": "synchronized",
            "execution_reconciliation_state": "clear",
            "execution_reconciliation_reason": "clear",
            "audit_integrity": "disabled",
            "audit_integrity_policy": "allow_unbound_legacy",
            "safety_state": "ok",
            "execution_reconciliation_reference": None,
        }
        recovered_incident = dict(incident)
        recovered_incident["outcome"] = {
            "status": "recovered",
            "action_result": {"accepted": True},
            "recovery_samples": [0.1, 0.0],
        }
        recovered = {
            **initial,
            "incident": recovered_incident,
            "recovery": {
                "state": "recovered",
                "action_accepted": True,
                "recheck_eligible": False,
                "verified": True,
                "sample_count": 2,
                "checkpoint_phase_consistent": True,
            },
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
            const initial = {json.dumps(initial)};
            const recovered = {json.dumps(recovered)};
            const ids = {json.dumps(ids)};
            const requests = [];

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
            global.fetch = async (path, init={{}}) => {{
              const method = init.method || 'GET';
              requests.push({{
                path,
                method,
                body: init.body ?? null,
                credentials: init.credentials ?? null,
                contentType: init.headers?.['Content-Type'] ?? null,
              }});
              let payload;
              if (path === '/v1/recovery/recheck' && method === 'POST') payload = recovered;
              else if (String(path).startsWith('/v1/audit?')) payload = {{timeline: {{events: [], next_after_sequence: 0, has_more: false}}}};
              else payload = initial;
              return {{
                ok: true,
                status: 200,
                json: async () => payload,
              }};
            }};

            process.on('unhandledRejection', error => {{ throw error; }});
            vm.runInThisContext(source, {{filename:'operator.js'}});

            setTimeout(async () => {{
              const before = {{
                recheckDisabled: elements['recheck-recovery'].disabled,
                executeDisabled: elements.execute.disabled,
                judgeRecovery: elements['judge-recovery'].textContent,
              }};
              await elements['recheck-recovery'].click();
              setTimeout(() => {{
                const out = {{
                  before,
                  after: {{
                    recheckDisabled: elements['recheck-recovery'].disabled,
                    executeDisabled: elements.execute.disabled,
                    judgeRecovery: elements['judge-recovery'].textContent,
                    recoveryText: elements.recovery.textContent,
                  }},
                  requests,
                }};
                process.stdout.write(JSON.stringify(out));
              }}, 20);
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
            self.fail(f"operator DOM request harness failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"operator DOM request harness returned invalid JSON: {proc.stdout!r}\n{proc.stderr}\n{exc}")

    def test_recheck_click_posts_only_to_recovery_endpoint_and_never_execute(self):
        result = self._run_recheck_click()

        self.assertFalse(result["before"]["recheckDisabled"])
        self.assertTrue(result["before"]["executeDisabled"])
        self.assertEqual("Recheck available · no provider replay", result["before"]["judgeRecovery"])

        mutations = [item for item in result["requests"] if item["method"] != "GET"]
        self.assertEqual(1, len(mutations), mutations)
        self.assertEqual("/v1/recovery/recheck", mutations[0]["path"])
        self.assertEqual("POST", mutations[0]["method"])
        self.assertEqual("{}", mutations[0]["body"])
        self.assertEqual("same-origin", mutations[0]["credentials"])
        self.assertEqual("application/json", mutations[0]["contentType"])
        self.assertFalse(any(item["path"] == "/v1/execute" for item in result["requests"]))

        self.assertTrue(result["after"]["recheckDisabled"])
        self.assertTrue(result["after"]["executeDisabled"])
        self.assertEqual("Verified by Grafana", result["after"]["judgeRecovery"])
        self.assertIn('"state": "recovered"', result["after"]["recoveryText"])
        self.assertIn('"verified": true', result["after"]["recoveryText"])


if __name__ == "__main__":
    unittest.main()
