#!/usr/bin/env python3
"""Credential-free acceptance rehearsal for StageGuard watchdog observability.

Requires the default Docker Compose stack. The script first attests that the
running Prometheus and Grafana versions match the repository's pinned
acceptance baseline, then drives only the local metrics fixture and proves two
independent Grafana safety contracts:

1. healthy -> remediation deadline firing -> healthy/resolved
2. healthy -> metrics unavailable -> stale-evidence warning -> telemetry restored

The outage path never changes remediation state. It also proves that stale
telemetry does not falsely activate the critical remediation-deadline alert.
The fixture is always restored to idle with telemetry online before exit.
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import math
import time
import urllib.parse
import urllib.request
from typing import Any


EXPECTED_PROMETHEUS_VERSION = "3.13.3"
EXPECTED_GRAFANA_VERSION = "13.2.1"
DEADLINE_ALERT_TITLE = "StageGuard remediation execution deadline exceeded"
DEADLINE_ALERT_SUMMARY = "StageGuard remediation execution exceeded its configured safety deadline"
STALE_ALERT_TITLE = "StageGuard runtime telemetry stale"
STALE_ALERT_SUMMARY = "StageGuard runtime watchdog telemetry is stale or missing"
METRIC = "stageguard_remediation_execution_deadline_exceeded"
FRESHNESS_QUERY = f"max(time() - timestamp({METRIC})) or vector(1000000000) * absent({METRIC})"
FRESHNESS_THRESHOLD_SECONDS = 45.0


def _require_loopback_http(value: str, name: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "http" or parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{name} must be a loopback http URL without user info")
    host = parsed.hostname
    if host is None:
        raise ValueError(f"{name} must include a host")
    is_loopback = host.lower() == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError(f"{name} must be a loopback service origin")
    return value.rstrip("/")


def _require_positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite positive number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def _request(url: str, *, method: str = "GET", auth: tuple[str, str] | None = None) -> bytes:
    headers = {"Accept": "application/json"}
    if auth is not None:
        raw = f"{auth[0]}:{auth[1]}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    request = urllib.request.Request(url, data=b"" if method == "POST" else None, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.read()


def prometheus_runtime_version_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ValueError("Prometheus build-info response must be a successful object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Prometheus build-info data must be an object")
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Prometheus build-info version must be a non-empty string")
    return version.strip()


def grafana_runtime_version_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Grafana health response must be an object")
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Grafana health version must be a non-empty string")
    return version.strip()


def prometheus_runtime_version(base: str) -> str:
    payload = json.loads(_request(f"{base}/api/v1/status/buildinfo").decode("utf-8"))
    return prometheus_runtime_version_from_payload(payload)


def grafana_runtime_version(base: str, auth: tuple[str, str]) -> str:
    payload = json.loads(_request(f"{base}/api/health", auth=auth).decode("utf-8"))
    return grafana_runtime_version_from_payload(payload)


def set_fixture(base: str, state: str) -> None:
    if state not in {"idle", "active", "overdue"}:
        raise ValueError("unsupported fixture state")
    _request(f"{base}/scenario/{state}", method="POST")


def set_telemetry(base: str, available: bool) -> None:
    if not isinstance(available, bool):
        raise TypeError("telemetry availability must be boolean")
    mode = "online" if available else "offline"
    _request(f"{base}/telemetry/{mode}", method="POST")


def prometheus_query_value(base: str, expression: str) -> float | None:
    query = urllib.parse.urlencode({"query": expression})
    payload = json.loads(_request(f"{base}/api/v1/query?{query}").decode("utf-8"))
    if payload.get("status") != "success":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    results = data.get("result", [])
    if not isinstance(results, list) or not results:
        return None
    value = results[0].get("value") if isinstance(results[0], dict) else None
    if not isinstance(value, list) or len(value) < 2:
        return None
    return float(value[1])


def prometheus_value(base: str) -> float | None:
    return prometheus_query_value(base, METRIC)


def prometheus_freshness_age(base: str) -> float | None:
    return prometheus_query_value(base, FRESHNESS_QUERY)


def _alert_matches(alert: dict[str, Any], *, title: str, summary: str) -> bool:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    if not isinstance(labels, dict) or not isinstance(annotations, dict):
        raise ValueError("Grafana alert labels/annotations must be objects")
    return labels.get("alertname") == title or annotations.get("summary") == summary


def grafana_alert_active_from_payload(payload: Any, *, title: str, summary: str) -> bool:
    """Return whether a validated active-alert payload contains the requested rule.

    Grafana's Alertmanager v2 alerts endpoint represents active alerts. An empty
    valid list therefore proves the rule is no longer active. Unexpected shapes
    raise instead of being interpreted as recovery, preventing malformed API
    responses from creating a false resolved result.
    """
    if not isinstance(payload, list):
        raise ValueError("Grafana active alerts response must be a list")
    for alert in payload:
        if not isinstance(alert, dict):
            raise ValueError("Grafana active alert entry must be an object")
        if _alert_matches(alert, title=title, summary=summary):
            return True
    return False


def grafana_active_alerts(base: str, auth: tuple[str, str]) -> Any:
    return json.loads(
        _request(f"{base}/api/alertmanager/grafana/api/v2/alerts", auth=auth).decode("utf-8")
    )


def deadline_alert_active(base: str, auth: tuple[str, str]) -> bool:
    return grafana_alert_active_from_payload(
        grafana_active_alerts(base, auth),
        title=DEADLINE_ALERT_TITLE,
        summary=DEADLINE_ALERT_SUMMARY,
    )


def stale_alert_active(base: str, auth: tuple[str, str]) -> bool:
    return grafana_alert_active_from_payload(
        grafana_active_alerts(base, auth),
        title=STALE_ALERT_TITLE,
        summary=STALE_ALERT_SUMMARY,
    )


def wait_until(predicate, *, timeout: float, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pass
        time.sleep(interval)
    return False


def _fail_if_deadline_alert_active(grafana: str, auth: tuple[str, str], context: str) -> bool:
    try:
        active = deadline_alert_active(grafana, auth)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print(f"FAIL: could not verify critical deadline alert state {context}")
        return False
    if active:
        print(f"FAIL: critical deadline alert falsely active {context}")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Rehearse StageGuard watchdog Prometheus/Grafana alerting")
    parser.add_argument("--fixture", default="http://127.0.0.1:9111")
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--grafana", default="http://127.0.0.1:3000")
    parser.add_argument("--grafana-user", default="admin")
    parser.add_argument("--grafana-password", default="stageguard-local-only")
    parser.add_argument("--prometheus-timeout", type=float, default=12.0)
    parser.add_argument("--alert-timeout", type=float, default=35.0)
    parser.add_argument("--resolve-timeout", type=float, default=35.0)
    parser.add_argument("--stale-timeout", type=float, default=95.0)
    args = parser.parse_args()
    for name in ("prometheus_timeout", "alert_timeout", "resolve_timeout", "stale_timeout"):
        try:
            _require_positive_finite(getattr(args, name), name)
        except ValueError as exc:
            parser.error(str(exc))
    try:
        fixture = _require_loopback_http(args.fixture, "fixture")
        prometheus = _require_loopback_http(args.prometheus, "prometheus")
        grafana = _require_loopback_http(args.grafana, "grafana")
    except ValueError as exc:
        parser.error(str(exc))
    auth = (args.grafana_user, args.grafana_password)

    # A stale local container can otherwise make a repository-pinned rehearsal
    # appear green against the wrong upstream runtime. Wait only for API
    # availability, then require exact version identity before driving state.
    if not wait_until(lambda: bool(prometheus_runtime_version(prometheus)), timeout=args.prometheus_timeout):
        print("FAIL: Prometheus build-info API did not become available")
        return 1
    if not wait_until(lambda: bool(grafana_runtime_version(grafana, auth)), timeout=args.prometheus_timeout):
        print("FAIL: Grafana health API did not become available")
        return 1
    try:
        live_prometheus = prometheus_runtime_version(prometheus)
        live_grafana = grafana_runtime_version(grafana, auth)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("FAIL: could not attest observability runtime versions")
        return 1
    if live_prometheus != EXPECTED_PROMETHEUS_VERSION:
        print(
            f"FAIL: Prometheus runtime version {live_prometheus!r} does not match "
            f"pinned acceptance version {EXPECTED_PROMETHEUS_VERSION!r}"
        )
        return 1
    if live_grafana != EXPECTED_GRAFANA_VERSION:
        print(
            f"FAIL: Grafana runtime version {live_grafana!r} does not match "
            f"pinned acceptance version {EXPECTED_GRAFANA_VERSION!r}"
        )
        return 1

    try:
        # First prove the genuine remediation-deadline lifecycle.
        set_telemetry(fixture, True)
        set_fixture(fixture, "idle")
        if not wait_until(lambda: prometheus_value(prometheus) == 0.0, timeout=args.prometheus_timeout):
            print("FAIL: Prometheus did not ingest the idle watchdog metric")
            return 1

        set_fixture(fixture, "overdue")
        if not wait_until(lambda: prometheus_value(prometheus) == 1.0, timeout=args.prometheus_timeout):
            print("FAIL: Prometheus did not ingest the overdue watchdog metric")
            return 1
        if not wait_until(lambda: deadline_alert_active(grafana, auth), timeout=args.alert_timeout):
            print("FAIL: Grafana watchdog deadline alert did not become active")
            return 1

        set_fixture(fixture, "idle")
        if not wait_until(lambda: prometheus_value(prometheus) == 0.0, timeout=args.prometheus_timeout):
            print("FAIL: Prometheus did not ingest the recovered watchdog metric")
            return 1
        if not wait_until(lambda: not deadline_alert_active(grafana, auth), timeout=args.resolve_timeout):
            print("FAIL: Grafana watchdog deadline alert did not resolve after recovery")
            return 1

        # Then interrupt metrics only. Remediation state remains idle throughout.
        set_telemetry(fixture, False)
        if not wait_until(
            lambda: (prometheus_freshness_age(prometheus) or 0.0) > FRESHNESS_THRESHOLD_SECONDS,
            timeout=args.stale_timeout,
        ):
            print("FAIL: Prometheus watchdog sample age did not cross the stale threshold")
            return 1
        if not _fail_if_deadline_alert_active(grafana, auth, "during telemetry outage"):
            return 1
        if not wait_until(lambda: stale_alert_active(grafana, auth), timeout=args.stale_timeout):
            print("FAIL: Grafana stale-telemetry warning did not become active")
            return 1
        if not _fail_if_deadline_alert_active(grafana, auth, "while stale warning was active"):
            return 1

        # Restore scraping and prove freshness + warning resolution.
        set_telemetry(fixture, True)
        if not wait_until(lambda: prometheus_value(prometheus) == 0.0, timeout=args.prometheus_timeout):
            print("FAIL: Prometheus did not resume watchdog metric ingestion")
            return 1
        if not wait_until(
            lambda: (prometheus_freshness_age(prometheus) is not None)
            and prometheus_freshness_age(prometheus) < FRESHNESS_THRESHOLD_SECONDS,
            timeout=args.prometheus_timeout,
        ):
            print("FAIL: Prometheus watchdog freshness did not recover")
            return 1
        if not wait_until(lambda: not stale_alert_active(grafana, auth), timeout=args.resolve_timeout):
            print("FAIL: Grafana stale-telemetry warning did not resolve after scraping resumed")
            return 1
        if not _fail_if_deadline_alert_active(grafana, auth, "after telemetry recovery"):
            return 1

        print(
            "PASS: pinned runtime versions attested; deadline alert fired/resolved; "
            "telemetry outage fired only stale warning and recovered cleanly"
        )
        return 0
    finally:
        try:
            set_telemetry(fixture, True)
            set_fixture(fixture, "idle")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
