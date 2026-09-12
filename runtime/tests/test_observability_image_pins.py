from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


class ObservabilityImagePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = COMPOSE.read_text(encoding="utf-8")
        cls.lines = cls.compose.splitlines()

    def _service_image(self, service: str) -> str:
        header = f"  {service}:"
        try:
            start = self.lines.index(header) + 1
        except ValueError as exc:
            self.fail(f"missing service {service}: {exc}")

        for line in self.lines[start:]:
            if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
                break
            stripped = line.strip()
            if stripped.startswith("image:"):
                image = stripped.partition(":")[2].strip()
                self.assertTrue(image, f"empty image for service {service}")
                return image

        self.fail(f"missing image for service {service}")

    def _service_block(self, service: str) -> str:
        header = f"  {service}:"
        try:
            start = self.lines.index(header)
        except ValueError as exc:
            self.fail(f"missing service {service}: {exc}")
        end = len(self.lines)
        for index in range(start + 1, len(self.lines)):
            line = self.lines[index]
            if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
                end = index
                break
        return "\n".join(self.lines[start:end])

    def test_prometheus_is_pinned_to_expected_lts_patch(self) -> None:
        self.assertEqual(self._service_image("prometheus"), "prom/prometheus:v3.13.3")

    def test_grafana_is_pinned_to_expected_stable_patch(self) -> None:
        self.assertEqual(self._service_image("grafana"), "grafana/grafana:13.2.1")

    def test_grafana_mcp_is_pinned_to_reviewed_patch(self) -> None:
        self.assertEqual(self._service_image("mcp"), "grafana/mcp-grafana:1.4.1")

    def test_grafana_mcp_retains_read_only_least_privilege_flags(self) -> None:
        block = self._service_block("mcp")
        self.assertIn("--disable-write", block)
        self.assertIn("--disable-proxied", block)
        self.assertIn("datasource,prometheus,loki", block)
        self.assertIn("--max-loki-log-limit", block)
        self.assertNotIn("--enable-write-tools", block)

    def test_observability_services_never_use_floating_latest_tag(self) -> None:
        for service in ("prometheus", "grafana", "mcp"):
            with self.subTest(service=service):
                image = self._service_image(service)
                self.assertNotEqual(image.rsplit(":", 1)[-1], "latest")

    def test_pin_rationale_is_kept_next_to_images(self) -> None:
        self.assertIn("Prometheus 3.13 is the current LTS line", self.compose)
        self.assertIn("Grafana alert provisioning and active-alert API behavior", self.compose)
        self.assertIn("Grafana MCP 1.4.1 was released", self.compose)
        self.assertIn("Sift labelSelector breaking change is outside this enabled", self.compose)


if __name__ == "__main__":
    unittest.main()
