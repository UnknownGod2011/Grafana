from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy_cloud_run.sh"
GEMINI = ROOT / "runtime" / "gemini_commander.py"
ENTRYPOINT = ROOT / "runtime" / "cloudrun_entrypoint.py"
DOCTOR = ROOT / "scripts" / "gcp_deploy_doctor.py"


class CloudRunDeployContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.deploy = DEPLOY.read_text(encoding="utf-8")
        cls.gemini = GEMINI.read_text(encoding="utf-8")
        cls.entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
        cls.doctor = DOCTOR.read_text(encoding="utf-8")

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

    def test_deploy_exposes_only_remediation_watchdog_tuning_not_write_enablement(self) -> None:
        setting = "STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS"
        self.assertIn(f'{setting}=${{{setting}}}', self.deploy)
        self.assertIn(f'if [[ -v {setting} ]]; then', self.deploy)
        self.assertIn(f'{setting}="60"', self.deploy)
        self.assertIn("must be a finite positive decimal number", self.deploy)
        self.assertLess(self.deploy.index(f'if [[ -v {setting} ]]'), self.deploy.index("gcloud run deploy"))
        self.assertNotIn("STAGEGUARD_ENABLE_REMEDIATION", self.deploy)

    def test_grafana_token_remains_secret_manager_file_mount(self) -> None:
        self.assertIn('/secrets/grafana-token=${GRAFANA_TOKEN_SECRET}:latest', self.deploy)
        self.assertIn('GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE=/secrets/grafana-token', self.deploy)
        self.assertNotIn('GRAFANA_SERVICE_ACCOUNT_TOKEN=', self.deploy)

    def test_cloud_run_requires_authenticated_durable_checkpoint_configuration(self) -> None:
        required_block = self.deploy.split('required=(', 1)[1].split(')', 1)[0]
        self.assertIn('CHECKPOINT_BUCKET', required_block)
        self.assertIn('CHECKPOINT_HMAC_SECRET', required_block)
        self.assertIn('STAGEGUARD_CHECKPOINT_BUCKET=${CHECKPOINT_BUCKET}', self.deploy)
        self.assertIn('STAGEGUARD_CHECKPOINT_OBJECT=${CHECKPOINT_OBJECT}', self.deploy)
        self.assertIn('CHECKPOINT_OBJECT="${CHECKPOINT_OBJECT:-stageguard/incident-checkpoint.json}"', self.deploy)

    def test_checkpoint_hmac_payload_is_resolved_by_secret_manager_not_literal_env_vars(self) -> None:
        self.assertIn('STAGEGUARD_CHECKPOINT_HMAC_KEY=${CHECKPOINT_HMAC_SECRET}:latest', self.deploy)
        env_vars_assignment = next(
            line for line in self.deploy.splitlines() if line.startswith('ENV_VARS=')
        )
        self.assertNotIn('STAGEGUARD_CHECKPOINT_HMAC_KEY', env_vars_assignment)
        self.assertNotIn('${STAGEGUARD_CHECKPOINT_HMAC_KEY}', self.deploy)

    def test_checkpoint_identifiers_are_validated_before_gcloud_deploy(self) -> None:
        deploy_index = self.deploy.index('gcloud run deploy')
        self.assertLess(self.deploy.index('CHECKPOINT_BUCKET is not a valid bounded GCS bucket name'), deploy_index)
        self.assertLess(self.deploy.index('CHECKPOINT_OBJECT is not a valid bounded object path'), deploy_index)

    def test_checkpoint_object_limit_is_utf8_bytes_across_deploy_doctor_and_runtime(self) -> None:
        self.assertIn("CHECKPOINT_OBJECT_BYTES", self.deploy)
        self.assertIn("LC_ALL=C", self.deploy)
        self.assertIn("wc -c", self.deploy)
        self.assertIn("at most 512 UTF-8 bytes", self.deploy)
        self.assertIn('len(name.encode("utf-8")) > 512', self.entrypoint)
        self.assertIn('len(name.encode("utf-8")) <= 512', self.doctor)
        self.assertNotIn('(( ${#CHECKPOINT_OBJECT} > 512 ))', self.deploy)

    def test_checkpoint_object_leading_and_trailing_whitespace_fail_before_deploy(self) -> None:
        deploy_index = self.deploy.index('gcloud run deploy')
        leading_guard = '"${CHECKPOINT_OBJECT}" =~ ^[[:space:]]'
        trailing_guard = '"${CHECKPOINT_OBJECT}" =~ [[:space:]]$'
        self.assertIn(leading_guard, self.deploy)
        self.assertIn(trailing_guard, self.deploy)
        self.assertLess(self.deploy.index(leading_guard), deploy_index)
        self.assertLess(self.deploy.index(trailing_guard), deploy_index)
        self.assertIn('name != raw', self.entrypoint)


if __name__ == "__main__":
    unittest.main()
