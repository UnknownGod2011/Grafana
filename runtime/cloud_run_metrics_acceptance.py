#!/usr/bin/env python3
"""Opt-in acceptance harness for StageGuard's private Cloud Run metrics path.

This command validates an already-provisioned private StageGuard Cloud Run
service using Application Default Credentials and an existing least-privilege
``roles/run.invoker`` grant.

Acceptance path:

    ADC ID token -> private Cloud Run /metrics -> local authenticated bridge
    -> bridge /readyz -> bridge /metrics -> disposable Prometheus -> up == 1
    -> stop only local bridge -> Prometheus up == 0
    -> authenticated Cloud Run /metrics still valid
    -> restart bridge on same port -> Prometheus up == 1

The bridge binds beyond loopback so Prometheus in Docker can reach the host.
For that reason this harness generates a fresh high-entropy bearer credential
for every run. The credential protects bridge /readyz and /metrics, is written
only into the temporary read-only Prometheus config, is never printed, and is
independent from the Google ID token used upstream.

The harness never creates IAM bindings, deploys services, writes persistent
secrets, prints credentials, calls StageGuard lifecycle endpoints, or triggers
remediation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from cloud_run_metrics_bridge import CloudRunMetricsClient, make_server, normalize_target

DEFAULT_PROMETHEUS_IMAGE = "prom/prometheus:v3.13.3"
DEFAULT_JOB_NAME = "stageguard-cloud-run-acceptance"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_PROMETHEUS_START_TIMEOUT_SECONDS = 45.0
DEFAULT_SCRAPE_TIMEOUT_SECONDS = 45.0
ALLOWED_UNAUTHORIZED_STATUSES = frozenset({401, 403})
MAX_JOB_NAME_LENGTH = 128
_JOB_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")


class AcceptanceError(RuntimeError):
    """Raised when the private metrics acceptance contract is not satisfied."""


@dataclass(frozen=True)
class AcceptanceResult:
    target_origin: str
    unauthorized_status: int
    bridge_port: int
    prometheus_up: float
    outage_up: float
    recovered_up: float


def normalize_job_name(value: str) -> str:
    """Return one unambiguous Prometheus job identity for the acceptance probe.

    The same value is embedded in generated YAML and in the exact PromQL
    selector used for the up/down/up proof. Restricting it to a deliberately
    small label-safe alphabet prevents config/query injection and accidental
    selectors that can broaden the acceptance target set.
    """
    if not isinstance(value, str) or not value or value != value.strip():
        raise AcceptanceError("Prometheus job name must be a non-empty trimmed string")
    if len(value) > MAX_JOB_NAME_LENGTH:
        raise AcceptanceError(f"Prometheus job name must be at most {MAX_JOB_NAME_LENGTH} characters")
    if _JOB_NAME_RE.fullmatch(value) is None:
        raise AcceptanceError("Prometheus job name contains unsupported characters")
    return value


def _request_status_without_redirects(url: str, timeout_seconds: float) -> int:
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, _req, _fp, _code, _msg, _headers, _newurl):
            return None

    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/plain", "User-Agent": "stageguard-metrics-acceptance/1"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def verify_unauthorized_upstream(metrics_url: str, timeout_seconds: float) -> int:
    status = _request_status_without_redirects(metrics_url, timeout_seconds)
    if status not in ALLOWED_UNAUTHORIZED_STATUSES:
        raise AcceptanceError(
            "unauthenticated upstream /metrics was not rejected with HTTP 401/403; "
            f"received HTTP {status}"
        )
    return status


def _bridge_request(url: str, bearer_token: str | None = None) -> urllib.request.Request:
    headers = {"Accept": "application/json"}
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return urllib.request.Request(url, headers=headers, method="GET")


def wait_for_bridge_ready(base_url: str, timeout_seconds: float, bearer_token: str | None = None) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            request = _bridge_request(f"{base_url}/readyz", bearer_token)
            with urllib.request.urlopen(request, timeout=2) as response:
                last_status = int(response.status)
                if response.status == 200 and response.read() == b'{"ok":true,"upstream":"reachable"}':
                    return
        except urllib.error.HTTPError as exc:
            last_status = int(exc.code)
        except OSError:
            pass
        time.sleep(0.5)
    suffix = f" (last HTTP status {last_status})" if last_status is not None else ""
    raise AcceptanceError(f"authenticated metrics bridge did not become ready{suffix}")


def wait_for_prometheus_up(
    prometheus_url: str,
    job_name: str,
    expected: float,
    timeout_seconds: float,
) -> float:
    """Wait for one finite Prometheus ``up`` sample equal to ``expected``."""
    job_name = normalize_job_name(job_name)
    if expected not in (0.0, 1.0):
        raise ValueError("expected Prometheus up value must be 0 or 1")
    query = urllib.parse.urlencode({"query": f'up{{job="{job_name}"}}'})
    url = f"{prometheus_url}/api/v1/query?{query}"
    deadline = time.monotonic() + timeout_seconds
    last_error = "no result"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") != "success":
                last_error = "Prometheus query did not report success"
            else:
                result = payload.get("data", {}).get("result")
                if not isinstance(result, list) or len(result) != 1:
                    last_error = "Prometheus query did not return exactly one target"
                else:
                    sample = result[0].get("value")
                    if not isinstance(sample, list) or len(sample) != 2:
                        last_error = "Prometheus returned a malformed up sample"
                    else:
                        try:
                            value = float(sample[1])
                        except (TypeError, ValueError):
                            last_error = "Prometheus returned a nonnumeric up sample"
                        else:
                            if math.isfinite(value) and value == expected:
                                return value
                            last_error = f"Prometheus up sample was {value!r}"
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc.__class__.__name__
        time.sleep(1.0)
    raise AcceptanceError(
        f"Prometheus never observed the StageGuard bridge as up={expected:g} ({last_error})"
    )


def fetch_prometheus_up(prometheus_url: str, job_name: str, timeout_seconds: float) -> float:
    return wait_for_prometheus_up(prometheus_url, job_name, 1.0, timeout_seconds)


def _prometheus_config(bridge_port: int, job_name: str, bearer_token: str | None = None) -> str:
    job_name = normalize_job_name(job_name)
    auth = ""
    if bearer_token is not None:
        # JSON strings are valid YAML scalars and avoid injection through a
        # generated or externally supplied token.
        auth = f"    authorization:\n      type: Bearer\n      credentials: {json.dumps(bearer_token)}\n"
    return (
        "global:\n"
        "  scrape_interval: 2s\n"
        "  scrape_timeout: 2s\n"
        "scrape_configs:\n"
        f"  - job_name: {json.dumps(job_name)}\n"
        f"{auth}"
        "    static_configs:\n"
        f"      - targets: ['host.docker.internal:{bridge_port}']\n"
    )


def _docker_available() -> None:
    if shutil.which("docker") is None:
        raise AcceptanceError("docker is required for the disposable Prometheus acceptance step")
    completed = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise AcceptanceError("docker daemon is unavailable for the disposable Prometheus acceptance step")


def _start_prometheus(config_path: Path, image: str) -> tuple[str, int]:
    command = [
        "docker",
        "run",
        "--detach",
        "--rm",
        "--add-host",
        "host.docker.internal:host-gateway",
        "--publish",
        "127.0.0.1::9090",
        "--volume",
        f"{config_path}:/etc/prometheus/prometheus.yml:ro",
        image,
        "--config.file=/etc/prometheus/prometheus.yml",
        "--storage.tsdb.path=/prometheus",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise AcceptanceError("could not start disposable Prometheus container")
    container_id = completed.stdout.strip()
    if not container_id:
        raise AcceptanceError("docker did not return a disposable Prometheus container id")
    inspect = subprocess.run(
        ["docker", "port", container_id, "9090/tcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if inspect.returncode != 0:
        _stop_container(container_id)
        raise AcceptanceError("could not discover disposable Prometheus host port")
    mapping = inspect.stdout.strip().splitlines()[0] if inspect.stdout.strip() else ""
    try:
        port = int(mapping.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        _stop_container(container_id)
        raise AcceptanceError("docker returned an unrecognized Prometheus port mapping")
    return container_id, port


def _stop_container(container_id: str) -> None:
    if not container_id:
        return
    subprocess.run(
        ["docker", "stop", "--time", "2", container_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )


def _start_bridge(
    client: CloudRunMetricsClient,
    port: int = 0,
    *,
    bearer_token: str | None = None,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = make_server(
        client,
        "0.0.0.0",
        port,
        allow_network_bind=True,
        bearer_token=bearer_token,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_bridge(server: ThreadingHTTPServer | None, thread: threading.Thread | None) -> None:
    if server is None:
        return
    server.shutdown()
    server.server_close()
    if thread is not None:
        thread.join(timeout=5)


def run_acceptance(
    target: str,
    *,
    audience: str | None = None,
    prometheus_image: str = DEFAULT_PROMETHEUS_IMAGE,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    prometheus_start_timeout_seconds: float = DEFAULT_PROMETHEUS_START_TIMEOUT_SECONDS,
    scrape_timeout_seconds: float = DEFAULT_SCRAPE_TIMEOUT_SECONDS,
    job_name: str = DEFAULT_JOB_NAME,
    client_factory: Callable[..., CloudRunMetricsClient] = CloudRunMetricsClient,
) -> AcceptanceResult:
    job_name = normalize_job_name(job_name)
    metrics_url, target_origin = normalize_target(target)
    unauthorized_status = verify_unauthorized_upstream(metrics_url, timeout_seconds)
    client = client_factory(target, audience=audience, timeout_seconds=timeout_seconds)
    client.fetch()

    _docker_available()
    # This credential protects only the local bridge. It is never used as the
    # Cloud Run audience credential and never leaves the temporary acceptance
    # boundary except in the read-only Prometheus config.
    bridge_bearer_token = secrets.token_urlsafe(32)
    server: ThreadingHTTPServer | None = None
    thread: threading.Thread | None = None
    container_id = ""
    try:
        server, thread = _start_bridge(client, bearer_token=bridge_bearer_token)
        bridge_port = int(server.server_address[1])
        wait_for_bridge_ready(
            f"http://127.0.0.1:{bridge_port}",
            timeout_seconds,
            bridge_bearer_token,
        )

        with tempfile.TemporaryDirectory(prefix="stageguard-prometheus-") as temp_dir:
            config_path = Path(temp_dir) / "prometheus.yml"
            config_path.write_text(
                _prometheus_config(bridge_port, job_name, bridge_bearer_token),
                encoding="utf-8",
            )
            container_id, prometheus_port = _start_prometheus(config_path, prometheus_image)
            prometheus_url = f"http://127.0.0.1:{prometheus_port}"
            effective_timeout = max(prometheus_start_timeout_seconds, scrape_timeout_seconds)
            prometheus_up = wait_for_prometheus_up(
                prometheus_url, job_name, 1.0, effective_timeout
            )

            _stop_bridge(server, thread)
            server = None
            thread = None
            outage_up = wait_for_prometheus_up(
                prometheus_url, job_name, 0.0, scrape_timeout_seconds
            )

            client.fetch()

            server, thread = _start_bridge(
                client,
                bridge_port,
                bearer_token=bridge_bearer_token,
            )
            wait_for_bridge_ready(
                f"http://127.0.0.1:{bridge_port}",
                timeout_seconds,
                bridge_bearer_token,
            )
            recovered_up = wait_for_prometheus_up(
                prometheus_url, job_name, 1.0, scrape_timeout_seconds
            )

        return AcceptanceResult(
            target_origin=target_origin,
            unauthorized_status=unauthorized_status,
            bridge_port=bridge_port,
            prometheus_up=prometheus_up,
            outage_up=outage_up,
            recovered_up=recovered_up,
        )
    finally:
        _stop_container(container_id)
        _stop_bridge(server, thread)


def _positive_finite(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a finite positive number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Opt-in acceptance for the authenticated private StageGuard Cloud Run metrics path"
    )
    parser.add_argument("--target", default=os.environ.get("STAGEGUARD_METRICS_TARGET"))
    parser.add_argument("--audience", default=os.environ.get("STAGEGUARD_METRICS_AUDIENCE"))
    parser.add_argument(
        "--prometheus-image",
        default=os.environ.get("STAGEGUARD_ACCEPTANCE_PROMETHEUS_IMAGE", DEFAULT_PROMETHEUS_IMAGE),
    )
    parser.add_argument("--timeout-seconds", type=_positive_finite, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--prometheus-start-timeout-seconds",
        type=_positive_finite,
        default=DEFAULT_PROMETHEUS_START_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--scrape-timeout-seconds",
        type=_positive_finite,
        default=DEFAULT_SCRAPE_TIMEOUT_SECONDS,
    )
    args = parser.parse_args()
    if not args.target:
        parser.error("--target or STAGEGUARD_METRICS_TARGET is required")
    try:
        result = run_acceptance(
            args.target,
            audience=args.audience,
            prometheus_image=args.prometheus_image,
            timeout_seconds=args.timeout_seconds,
            prometheus_start_timeout_seconds=args.prometheus_start_timeout_seconds,
            scrape_timeout_seconds=args.scrape_timeout_seconds,
        )
    except AcceptanceError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: acceptance aborted ({exc.__class__.__name__})")
        return 1

    print("PASS: private Cloud Run metrics acceptance")
    print(f"  target: {result.target_origin}")
    print(f"  unauthenticated /metrics: rejected ({result.unauthorized_status})")
    print("  ADC-authenticated /metrics: valid StageGuard sentinel")
    print("  local bridge: ephemeral bearer protection enabled")
    print("  bridge /readyz: healthy")
    print("  bridge /metrics: validated")
    print(f"  Prometheus {DEFAULT_JOB_NAME} initial up: {result.prometheus_up:g}")
    print(f"  local bridge outage up: {result.outage_up:g}")
    print("  upstream remained authenticated and valid during local outage")
    print(f"  local bridge recovered up: {result.recovered_up:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())