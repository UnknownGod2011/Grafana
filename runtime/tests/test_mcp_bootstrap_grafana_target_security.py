from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from bootstrap_grafana import _validate_bootstrap_target


class BootstrapGrafanaTargetSecurityTests(unittest.TestCase):
    def test_loopback_http_is_allowed_without_remote_opt_in(self) -> None:
        for url in (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://127.255.255.254:3000",
            "http://[::1]:3000",
            "http://[0:0:0:0:0:0:0:1]:3000",
        ):
            with self.subTest(url=url):
                _validate_bootstrap_target(url, allow_remote=False)

    def test_remote_target_requires_explicit_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "Refusing to create credentials on remote Grafana host"):
            _validate_bootstrap_target("https://grafana.example.test", allow_remote=False)

    def test_remote_http_is_rejected_even_with_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires HTTPS"):
            _validate_bootstrap_target("http://grafana.example.test", allow_remote=True)

    def test_remote_https_is_allowed_with_explicit_opt_in(self) -> None:
        _validate_bootstrap_target("https://grafana.example.test", allow_remote=True)

    def test_embedded_credentials_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "without embedded credentials"):
            _validate_bootstrap_target("https://admin:secret@grafana.example.test", allow_remote=True)

    def test_non_http_scheme_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "http\(s\) origin"):
            _validate_bootstrap_target("file:///tmp/grafana", allow_remote=True)

    def test_missing_host_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "http\(s\) origin"):
            _validate_bootstrap_target("https:///grafana", allow_remote=True)

    def test_origin_path_query_and_fragment_are_rejected(self) -> None:
        for url in (
            "https://grafana.example.test/grafana",
            "https://grafana.example.test/?tenant=prod",
            "https://grafana.example.test/#admin",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "without a path, query, or fragment"):
                    _validate_bootstrap_target(url, allow_remote=True)

    def test_malformed_or_out_of_range_ports_are_rejected(self) -> None:
        for url in (
            "https://grafana.example.test:not-a-port",
            "https://grafana.example.test:0",
            "https://grafana.example.test:65536",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "malformed|port is invalid"):
                    _validate_bootstrap_target(url, allow_remote=True)

    def test_localhost_lookalike_is_not_treated_as_loopback(self) -> None:
        with self.assertRaisesRegex(ValueError, "Refusing to create credentials on remote Grafana host"):
            _validate_bootstrap_target("http://localhost.example.test:3000", allow_remote=False)


if __name__ == "__main__":
    unittest.main()