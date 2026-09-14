from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = ROOT / "runtime" / "api.py"
API_DOC = ROOT / "API.md"


class HttpSurfaceContractTests(unittest.TestCase):
    """Keep safety-critical runtime routes and the public API contract aligned.

    This is intentionally a dependency-free static contract test. It does not
    replace behavioral HTTP tests; it prevents operator documentation from
    silently omitting the no-replay recovery/reconciliation paths.
    """

    PLATFORM_ROUTES = {
        "/healthz",
        "/readyz",
        "/metrics",
    }
    AUTHENTICATED_READ_ROUTES = {
        "/console",
        "/assets/operator.css",
        "/assets/operator.js",
        "/v1/incident",
        "/v1/audit",
    }
    LIFECYCLE_MUTATION_ROUTES = {
        "/v1/investigate",
        "/v1/briefing",
        "/v1/approve",
        "/v1/execute",
        "/v1/recovery/recheck",
        "/v1/checkpoint/reload",
        "/v1/execution/reconcile",
    }

    def setUp(self):
        self.source = API_SOURCE.read_text(encoding="utf-8")
        self.documentation = API_DOC.read_text(encoding="utf-8")

    def test_every_contract_route_exists_in_runtime_and_documentation(self):
        for route in sorted(
            self.PLATFORM_ROUTES
            | self.AUTHENTICATED_READ_ROUTES
            | self.LIFECYCLE_MUTATION_ROUTES
        ):
            with self.subTest(route=route):
                self.assertIn(route, self.source)
                self.assertIn(route, self.documentation)

    def test_no_replay_routes_are_explicitly_documented(self):
        self.assertIn("Never use `/v1/execute` to recover from `execution_uncertain`", self.documentation)
        self.assertIn("`POST /v1/recovery/recheck` is the only follow-up mutation", self.documentation)
        self.assertIn("cannot replay the external side effect", self.documentation)
        self.assertIn("cannot supply an operation ID or provider state", self.documentation)

    def test_reconciliation_and_recovery_remain_argument_free_in_runtime(self):
        for route in (
            "/v1/recovery/recheck",
            "/v1/checkpoint/reload",
            "/v1/execution/reconcile",
        ):
            marker = f'if self.path == "{route}":'
            with self.subTest(route=route):
                start = self.source.find(marker)
                self.assertGreaterEqual(start, 0)
                block = self.source[start : start + 260]
                self.assertIn("_only(payload, set())", block)


if __name__ == "__main__":
    unittest.main()
