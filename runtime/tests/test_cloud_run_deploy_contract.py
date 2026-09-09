from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy_cloud_run.sh"
GEMINI = ROOT / "runtime" / "gemini_commander.py"


class CloudRunDeployContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.deploy = DEPLOY.read_text(encoding="utf-8")
        cls.gemini = GEMINI.read_text(encoding="utf-8")

    def test_deploy_forwards_project_required_by_vertex_commander(self) -> None:
        self.assertIn('GOOGLE_CLOUD_PROJECT=${PROJECT_ID}', self.deploy)
        self.assertIn('os.environ.get("GOOGLE_CLOUD_PROJECT", "")', self.gemini)

    def test_deploy_forwards_vertex_location_and_model_with_runtime_defaults(self) -> None:
        self.assertIn('GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"', self.deploy)
        self.assertIn('STAGEGUARD_GEMINI_MODEL="${STAGEGUARD_GEMINI_MODEL:-gemini-2.5-flash}"', self.deploy)
        self.assertIn('GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}', self.deploy)
        self.assertIn('STAGEGUARD_GEMINI_MODEL=${STAGEGUARD_GEMINI_MODEL}', self.deploy)
        self.assertIn('os.environ.get("GOOGLE_CLOUD_LOCATION", "global")', self.gemini)
        self.assertIn('os.environ.get("STAGEGUARD_GEMINI_MODEL", "gemini-2.5-flash")', self.gemini)

    def test_vertex_env_values_are_guarded_against_set_env_vars_delimiter_injection(self) -> None:
        self.assertRegex(
            self.deploy,
            re.compile(r'for name in GOOGLE_CLOUD_LOCATION STAGEGUARD_GEMINI_MODEL; do.*?\*","\*.*?\[\[:space:\]\]', re.DOTALL),
        )

    def test_standard_cloud_run_artifact_still_has_no_production_remediation_configuration(self) -> None:
        forbidden = (
            "STAGEGUARD_ENABLE_REMEDIATION",
            "STAGEGUARD_REMEDIATION_ENDPOINT",
            "STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT",
            "STAGEGUARD_REMEDIATION_TOKEN",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertNotIn(name, self.deploy)

    def test_grafana_token_remains_secret_manager_file_mount(self) -> None:
        self.assertIn('/secrets/grafana-token=${GRAFANA_TOKEN_SECRET}:latest', self.deploy)
        self.assertIn('GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE=/secrets/grafana-token', self.deploy)
        self.assertNotIn('GRAFANA_SERVICE_ACCOUNT_TOKEN=', self.deploy)


if __name__ == "__main__":
    unittest.main()
