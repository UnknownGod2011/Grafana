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
        for url in ("http://localhost:3000", "http://127.0.0.1:3000", "http://[::1]:3000"):
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


if __name__ == "__main__":
    unittest.main()