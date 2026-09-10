#!/usr/bin/env python3
"""Credential-free acceptance rehearsal for StageGuard watchdog observability.

Requires the default Docker Compose stack. The script drives only the local
metrics fixture, proves Prometheus ingests the deadline series, and observes the
Grafana-managed alert transition through Grafana's Alertmanager API. It always
returns the fixture to idle before exiting.
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request


ALERT_TITLE = "StageGuard remediation execution deadline exceeded"
METRIC = "stageguard_remediation_execution_deadline_exceeded"


def _request(url: str, *, method: str = "GET", auth: tuple[str, str] | None = None) -> bytes:
    headers = {"Accept": "application/json"}
    if auth is not None:
        raw = f"{auth[0]}:{auth[1]}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    request = urllib.request.Request(url, data=b"" if method == "POST" else None, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.read()


def set_fixture(base: str, state: str) -> None:
    if state not in {"idle", "active", "overdue"}:
        raise ValueError("unsupported fixture state")
    _request(f"{base.rstrip('/')}/scenario/{state}", method="POST")


def prometheus_value(base: str) -> float | None:
    query = urllib.parse.urlencode({"query": METRIC})
    payload = json.loads(_request(f"{base.rstrip('/')}/api/v1/query?{query}").decode("utf-8"))
    if payload.get("status") != "success":
        return None
    results = payload.get("data", {}).get("result", [])
    if not results:
        return None
    return float(results[0]["value"][1])


def grafana_alert_firing(base: str, auth: tuple[str, str]) -> bool:
    payload = json.loads(
        _request(f"{base.rstrip('/')}/api/alertmanager/grafana/api/v2/alerts", auth=auth).decode("utf-8")
    )
    if not isinstance(payload, list):
        return False
    for alert in payload:
        labels = alert.get("labels", {}) if isinstance(alert, dict) else {}
        annotations = alert.get("annotations", {}) if isinstance(alert, dict) else {}
        if labels.get("alertname") == ALERT_TITLE or annotations.get("summary") == (
            "StageGuard remediation execution exceeded its configured safety deadline"
        ):
            return True
    return False


def wait_until(predicate, *, timeout: float, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
        time.sleep(interval)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Rehearse StageGuard watchdog Prometheus/Grafana alerting")
    parser.add_argument("--fixture", default="http://127.0.0.1:9111")
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--grafana", default="http://127.0.0.1:3000")
    parser.add_argument("--grafana-user", default="admin")
    parser.add_argument("--grafana-password", default="stageguard-local-only")
    parser.add_argument("--prometheus-timeout", type=float, default=12.0)
    parser.add_argument("--alert-timeout", type=float, default=35.0)
    args = parser.parse_args()
    auth = (args.grafana_user, args.grafana_password)

    try:
        set_fixture(args.fixture, "idle")
        if not wait_until(lambda: prometheus_value(args.prometheus) == 0.0, timeout=args.prometheus_timeout):
            print("FAIL: Prometheus did not ingest the idle watchdog metric")
            return 1

        set_fixture(args.fixture, "overdue")
        if not wait_until(lambda: prometheus_value(args.prometheus) == 1.0, timeout=args.prometheus_timeout):
            print("FAIL: Prometheus did not ingest the overdue watchdog metric")
            return 1

        if not wait_until(lambda: grafana_alert_firing(args.grafana, auth), timeout=args.alert_timeout):
            print("FAIL: Grafana watchdog alert did not become active")
            return 1

        print("PASS: watchdog metric reached Prometheus and Grafana alert became active")
        return 0
    finally:
        try:
            set_fixture(args.fixture, "idle")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
