"""Real-browser acceptance for the post-remediation no-replay operator state.

This suite is intentionally optional: it uses Playwright when installed, but does
not make the core StageGuard runtime depend on browser automation. Run from the
repository's ``runtime`` directory with:

    python -m pip install playwright
    python -m playwright install chromium
    python -m unittest tests.test_operator_browser_execution_uncertain

The fixture drives a real ExecutionSafeIncidentService through diagnosis,
approval, provider dispatch, successful recovery verification, and then a
simulated checkpoint persistence failure. The authenticated console must render
the resulting dual fail-closed state without exposing provider detail or
re-enabling any unsafe lifecycle action.
"""

import threading
import unittest

from api import make_server
from execution_safety import ExecutionSafeIncidentService
from identity import StaticBearerIdentityProvider
from incident_service import MemoryAuditLog
from remediation import ActionResult, remediation_operation_id

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised only when optional dependency is absent.
    sync_playwright = None


PROVIDER_SECRET_SENTINEL = "provider-token=browser-no-replay-secret"
PROVIDER_ENDPOINT_SENTINEL = "private-remediation-provider.example"


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class ProviderWithSensitiveMetadata:
    def __init__(self):
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(
            True,
            "accepted",
            {
                "provider_url": PROVIDER_ENDPOINT_SENTINEL,
                "provider_token": PROVIDER_SECRET_SENTINEL,
            },
        )


class FailSelectedSaveStore:
    """Retain the durable approval while the post-provider outcome save fails."""

    def __init__(self, fail_on_save):
        self.fail_on_save = fail_on_save
        self.save_calls = 0
        self.current = None

    def load(self):
        return self.current

    def save(self, checkpoint):
        self.save_calls += 1
        if self.save_calls == self.fail_on_save:
            raise RuntimeError("simulated checkpoint storage failure")
        self.current = checkpoint


def diagnosed_then_recovered():
    # Investigation: symptom, causal uplink A/B, contradiction CPU/GPU,
    # healthy-peer controls. Recovery: fresh loss/drop checks.
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1, 0.2, 0.2, 0.1, 0.1]


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class ExecutionUncertainBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = FailSelectedSaveStore(fail_on_save=3)
        cls.remediation = ProviderWithSensitiveMetadata()
        cls.service = ExecutionSafeIncidentService(
            SequenceMetrics(diagnosed_then_recovered()),
            cls.remediation,
            MemoryAuditLog(),
            checkpoint_store=cls.store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-browser-execution-uncertain",
            recovery_sleep=lambda _: None,
        )

        investigated = cls.service.investigate(actor="operator-browser-test")
        approved = cls.service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator-browser-test",
        )
        cls.expected_reference = remediation_operation_id(
            approved.report,
            approved.approval,
        )

        try:
            cls.service.execute_approved(actor="operator-browser-test")
        except RuntimeError as exc:
            if "simulated checkpoint storage failure" not in str(exc):
                raise
        else:
            raise AssertionError("browser fixture must fail final checkpoint persistence")

        if len(cls.remediation.calls) != 1:
            raise AssertionError("browser fixture must dispatch remediation exactly once")
        if cls.service.status().outcome is not None:
            raise AssertionError("failed persistence must not publish a remediation outcome")
        if cls.service.checkpoint_state() != "execution_uncertain":
            raise AssertionError("browser fixture must enter execution uncertainty")
        if cls.service.audit_integrity_state() != "failed":
            raise AssertionError("browser fixture must fail audit integrity")

        provider = StaticBearerIdentityProvider({"browser-token": "operator-browser-test"})
        cls.server = make_server(
            cls.service,
            "127.0.0.1",
            0,
            identity_provider=provider,
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_dual_failure_renders_do_not_replay_and_keeps_mutations_disabled(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                extra_http_headers={"Authorization": "Bearer browser-token"}
            )
            page = context.new_page()
            try:
                page.goto(
                    f"http://127.0.0.1:{self.port}/console",
                    wait_until="networkidle",
                )

                safety = page.locator("#execution-safety")
                safety.wait_for(state="visible")
                self.assertEqual(
                    "DO NOT REPLAY REMEDIATION",
                    page.locator("#execution-safety-title").inner_text(),
                )
                self.assertIn(
                    "may already have executed",
                    page.locator("#execution-safety-audit").inner_text(),
                )
                self.assertEqual(
                    self.expected_reference,
                    page.locator("#execution-reconciliation-reference").inner_text(),
                )

                # The dual safety state is stronger than any prior approval state.
                page.locator("#judge-state").wait_for(state="visible")
                self.assertEqual("DO NOT REPLAY", page.locator("#judge-state").inner_text())

                for selector in (
                    "#investigate",
                    "#briefing",
                    "#approval-revision",
                    "#approve",
                    "#execute",
                ):
                    with self.subTest(selector=selector):
                        self.assertTrue(page.locator(selector).is_disabled())

                self.assertEqual(
                    1,
                    len(self.remediation.calls),
                    "rendering the console must never replay provider remediation",
                )

                rendered = page.locator("body").inner_text()
                html = page.content()
                for sentinel in (
                    PROVIDER_SECRET_SENTINEL,
                    PROVIDER_ENDPOINT_SENTINEL,
                    "browser-no-replay-secret",
                ):
                    with self.subTest(sentinel=sentinel):
                        self.assertNotIn(sentinel, rendered)
                        self.assertNotIn(sentinel, html)

                # The only operation correlation value allowed into the browser is
                # the bounded StageGuard-generated reconciliation reference.
                self.assertIn(self.expected_reference, rendered)
                self.assertNotIn("provider_url", rendered)
                self.assertNotIn("provider_token", rendered)
            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    unittest.main()
