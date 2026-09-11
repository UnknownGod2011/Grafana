"""Real-browser acceptance for the evidence-plane unavailable operator state.

This suite is intentionally optional: it uses Playwright when installed, but does
not make the core StageGuard runtime depend on a browser automation package.
Run with:

    python -m pip install playwright
    python -m playwright install chromium
    python -m unittest runtime.tests.test_operator_browser_evidence_unavailable

The test starts the real authenticated StageGuard HTTP server, creates a real
abstained incident through IncidentService, and lets the shipped operator assets
fetch/render that state in Chromium.
"""

import threading
import unittest

from api import make_server
from evidence_errors import EvidenceUnavailable
from identity import StaticBearerIdentityProvider
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised only when optional dependency is absent.
    sync_playwright = None


PROVIDER_SECRET_SENTINEL = "provider-token=browser-secret-sentinel"
PROVIDER_ENDPOINT_SENTINEL = "private-browser-provider.example"


class FailingMetrics:
    """Produce one symptom sample, then make required causal evidence unavailable."""

    def __init__(self) -> None:
        self.calls = 0

    def instant(self, _query):
        self.calls += 1
        if self.calls == 1:
            return 4.0
        raise EvidenceUnavailable(
            f"{PROVIDER_SECRET_SENTINEL} upstream={PROVIDER_ENDPOINT_SENTINEL}"
        )


class NoopRemediation:
    def __init__(self) -> None:
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "accepted")


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class EvidenceUnavailableBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = FailingMetrics()
        cls.remediation = NoopRemediation()
        cls.service = IncidentService(
            cls.metrics,
            cls.remediation,
            MemoryAuditLog(),
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-browser-evidence-unavailable",
            recovery_sleep=lambda _: None,
        )
        snapshot = cls.service.investigate(actor="operator-browser-test")
        if snapshot.report.status != "abstain":
            raise AssertionError("browser fixture must create an abstained incident")

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

    def test_abstained_snapshot_renders_fail_closed_without_provider_detail(self):
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

                safety = page.locator("#evidence-unavailable-safety")
                safety.wait_for(state="visible")
                self.assertIn("Evidence plane unavailable", safety.inner_text())
                self.assertIn("Grafana", safety.inner_text())

                # Every advisory or mutation affordance must remain fail-closed.
                for selector in (
                    "#briefing",
                    "#approval-revision",
                    "#approve",
                    "#execute",
                ):
                    with self.subTest(selector=selector):
                        self.assertTrue(page.locator(selector).is_disabled())

                self.assertEqual("Not established", page.locator("#hypothesis").inner_text())
                self.assertEqual([], self.remediation.calls)

                rendered = page.locator("body").inner_text()
                html = page.content()
                for sentinel in (
                    PROVIDER_SECRET_SENTINEL,
                    PROVIDER_ENDPOINT_SENTINEL,
                    "browser-secret-sentinel",
                ):
                    with self.subTest(sentinel=sentinel):
                        self.assertNotIn(sentinel, rendered)
                        self.assertNotIn(sentinel, html)

                # The judge/proof layer must agree with the authoritative cockpit.
                page.locator("#judge-state").wait_for(state="visible")
                self.assertEqual(
                    "EVIDENCE UNAVAILABLE",
                    page.locator("#judge-state").inner_text(),
                )
                self.assertEqual(
                    "Not established",
                    page.locator("#judge-root-cause").inner_text(),
                )
            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    unittest.main()
