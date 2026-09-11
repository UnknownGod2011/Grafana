from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import cloud_run_metrics_acceptance as acceptance  # noqa: E402


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = io.BytesIO(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class CloudRunMetricsAcceptanceTests(unittest.TestCase):
    def test_unauthorized_upstream_requires_401_or_403(self) -> None:
        for status in (401, 403):
            with self.subTest(status=status):
                with mock.patch.object(acceptance, "_request_status_without_redirects", return_value=status):
                    self.assertEqual(
                        acceptance.verify_unauthorized_upstream("https://stageguard.example/metrics", 2),
                        status,
                    )

        for status in (200, 204, 302, 404, 500):
            with self.subTest(status=status):
                with mock.patch.object(acceptance, "_request_status_without_redirects", return_value=status):
                    with self.assertRaises(acceptance.AcceptanceError):
                        acceptance.verify_unauthorized_upstream("https://stageguard.example/metrics", 2)

    def test_prometheus_config_scrapes_only_local_bridge(self) -> None:
        config = acceptance._prometheus_config(49123, acceptance.DEFAULT_JOB_NAME)
        self.assertIn("job_name: 'stageguard-cloud-run-acceptance'", config)
        self.assertIn("host.docker.internal:49123", config)
        self.assertNotIn("stageguard.example", config)
        self.assertNotIn("Authorization", config)
        self.assertNotIn("bearer", config.lower())

    def test_prometheus_query_requires_exactly_one_up_sample_equal_to_one(self) -> None:
        good = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"job": acceptance.DEFAULT_JOB_NAME},
                        "value": [1234, "1"],
                    }
                ]
            },
        }
        with mock.patch.object(acceptance.urllib.request, "urlopen", return_value=_Response(json.dumps(good).encode())):
            self.assertEqual(
                acceptance.fetch_prometheus_up("http://127.0.0.1:9090", acceptance.DEFAULT_JOB_NAME, 0.1),
                1.0,
            )

    def test_prometheus_query_rejects_ambiguous_target_set(self) -> None:
        ambiguous = {
            "status": "success",
            "data": {
                "result": [
                    {"metric": {"instance": "a"}, "value": [1234, "1"]},
                    {"metric": {"instance": "b"}, "value": [1234, "1"]},
                ]
            },
        }
        with mock.patch.object(acceptance.urllib.request, "urlopen", return_value=_Response(json.dumps(ambiguous).encode())):
            with mock.patch.object(acceptance.time, "sleep", return_value=None):
                with self.assertRaises(acceptance.AcceptanceError):
                    acceptance.fetch_prometheus_up("http://127.0.0.1:9090", acceptance.DEFAULT_JOB_NAME, 0.001)

    def test_prometheus_query_rejects_nonfinite_and_down_samples(self) -> None:
        for sample in ("0", "NaN", "Inf", "-Inf", "nope"):
            payload = {
                "status": "success",
                "data": {"result": [{"metric": {}, "value": [1234, sample]}]},
            }
            with self.subTest(sample=sample):
                with mock.patch.object(
                    acceptance.urllib.request,
                    "urlopen",
                    return_value=_Response(json.dumps(payload).encode()),
                ):
                    with mock.patch.object(acceptance.time, "sleep", return_value=None):
                        with self.assertRaises(acceptance.AcceptanceError):
                            acceptance.fetch_prometheus_up(
                                "http://127.0.0.1:9090",
                                acceptance.DEFAULT_JOB_NAME,
                                0.001,
                            )

    def test_docker_preflight_does_not_include_credentials(self) -> None:
        completed = mock.Mock(returncode=1, stdout="", stderr="provider-secret-never-surface")
        with mock.patch.object(acceptance.shutil, "which", return_value="/usr/bin/docker"):
            with mock.patch.object(acceptance.subprocess, "run", return_value=completed) as run:
                with self.assertRaisesRegex(acceptance.AcceptanceError, "docker daemon is unavailable") as caught:
                    acceptance._docker_available()
        rendered = str(caught.exception)
        self.assertNotIn("provider-secret", rendered)
        flattened = " ".join(run.call_args.args[0])
        self.assertNotIn("token", flattened.lower())
        self.assertNotIn("credential", flattened.lower())

    def test_prometheus_container_is_ephemeral_and_read_only_config(self) -> None:
        run_result = mock.Mock(returncode=0, stdout="container-id\n", stderr="")
        port_result = mock.Mock(returncode=0, stdout="127.0.0.1:49152\n", stderr="")
        with mock.patch.object(acceptance.subprocess, "run", side_effect=[run_result, port_result]) as run:
            container_id, port = acceptance._start_prometheus(Path("/tmp/prometheus.yml"), "prom/prometheus:test")
        self.assertEqual(container_id, "container-id")
        self.assertEqual(port, 49152)
        command = run.call_args_list[0].args[0]
        self.assertIn("--rm", command)
        self.assertIn("127.0.0.1::9090", command)
        volume = command[command.index("--volume") + 1]
        self.assertTrue(volume.endswith(":/etc/prometheus/prometheus.yml:ro"))
        self.assertNotIn("--privileged", command)
        self.assertNotIn("--network", command)

    def test_cli_failure_sanitizes_unexpected_provider_exception_text(self) -> None:
        argv = ["cloud_run_metrics_acceptance.py", "--target", "https://stageguard.example"]
        secret = "token=super-secret https://private-provider.example"
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(acceptance, "run_acceptance", side_effect=RuntimeError(secret)):
                with mock.patch("builtins.print") as printer:
                    self.assertEqual(acceptance.main(), 1)
        output = "\n".join(" ".join(str(part) for part in call.args) for call in printer.call_args_list)
        self.assertIn("RuntimeError", output)
        self.assertNotIn("super-secret", output)
        self.assertNotIn("private-provider", output)


if __name__ == "__main__":
    unittest.main()
