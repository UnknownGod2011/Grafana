from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from bootstrap import _production_remediation_from_env
from http_remediation_transport import HttpRemediationTransport
from telemetry import DEFAULT_TELEMETRY_PROFILE


class ProductionReconciliationBootstrapTests(unittest.TestCase):
    def test_explicit_production_remediation_requires_reconciliation_endpoint(self) -> None:
        env = {
            "STAGEGUARD_REMEDIATION_ENDPOINT": "https://writer.example/v1/recover",
            "STAGEGUARD_REMEDIATION_TOKEN": "write-secret",
        }
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            ValueError, "STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT"
        ):
            _production_remediation_from_env(
                DEFAULT_TELEMETRY_PROFILE,
                endpoint_env="STAGEGUARD_REMEDIATION_ENDPOINT",
                reconciliation_endpoint_env="STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT",
                token_env="STAGEGUARD_REMEDIATION_TOKEN",
            )

    def test_explicit_production_remediation_wires_separate_read_endpoint(self) -> None:
        env = {
            "STAGEGUARD_REMEDIATION_ENDPOINT": "https://writer.example/v1/recover",
            "STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT": "https://reader.example/v1/operations",
            "STAGEGUARD_REMEDIATION_TOKEN": "write-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            client = _production_remediation_from_env(
                DEFAULT_TELEMETRY_PROFILE,
                endpoint_env="STAGEGUARD_REMEDIATION_ENDPOINT",
                reconciliation_endpoint_env="STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT",
                token_env="STAGEGUARD_REMEDIATION_TOKEN",
            )

        transport = client._transport
        self.assertIsInstance(transport, HttpRemediationTransport)
        self.assertEqual(transport.endpoint, "https://writer.example/v1/recover")
        self.assertEqual(
            transport.reconciliation_endpoint,
            "https://reader.example/v1/operations",
        )
        self.assertNotEqual(transport.endpoint, transport.reconciliation_endpoint)

    def test_invalid_reconciliation_endpoint_fails_before_any_network_call(self) -> None:
        env = {
            "STAGEGUARD_REMEDIATION_ENDPOINT": "https://writer.example/v1/recover",
            "STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT": "http://reader.example/v1/operations",
            "STAGEGUARD_REMEDIATION_TOKEN": "write-secret",
        }
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(ValueError, "must use HTTPS"):
            _production_remediation_from_env(
                DEFAULT_TELEMETRY_PROFILE,
                endpoint_env="STAGEGUARD_REMEDIATION_ENDPOINT",
                reconciliation_endpoint_env="STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT",
                token_env="STAGEGUARD_REMEDIATION_TOKEN",
            )


if __name__ == "__main__":
    unittest.main()
