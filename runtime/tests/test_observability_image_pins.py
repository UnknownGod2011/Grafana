from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


class ObservabilityImagePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = COMPOSE.read_text(encoding="utf-8")

    def _service_image(self, service: str) -> str:
        pattern = rf"(?ms)^  {re.escape(service)}:\n(?:^(?:    .*|\s*)$\n)*?^    image:\s*(\S+)\s*$"
        match = re.search(pattern, self.compose)
        self.assertIsNotNone(match, f"missing image for service {service}")
        assert match is not None
        return match.group(1)

    def test_prometheus_is_pinned_to_expected_lts_patch(self) -> None:
        self.assertEqual(self._service_image("prometheus"), "prom/prometheus:v3.13.3")

    def test_grafana_is_pinned_to_expected_stable_patch(self) -> None:
        self.assertEqual(self._service_image("grafana"), "grafana/grafana:13.2.1")

    def test_observability_services_never_use_floating_latest_tag(self) -> None:
        for service in ("prometheus", "grafana", "mcp"):
            with self.subTest(service=service):
                image = self._service_image(service)
                self.assertNotEqual(image.rsplit(":", 1)[-1], "latest")
                self.assertNotIn("@sha256:", image.split(":latest", 1)[0] if ":latest" in image else "")

    def test_pin_rationale_is_kept_next_to_images(self) -> None:
        self.assertIn("Prometheus 3.13 is the current LTS line", self.compose)
        self.assertIn("Grafana alert provisioning and active-alert API behavior", self.compose)


if __name__ == "__main__":
    unittest.main()
