from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "runtime" / "grafana" / "dashboards" / "stageguard-lifecycle.json"


def _dashboard() -> dict:
    return json.loads(DASHBOARD.read_text(encoding="utf-8"))


def _expressions(document: dict) -> list[str]:
    return [
        target.get("expr", "")
        for panel in document["panels"]
        for target in panel.get("targets", [])
    ]


def test_lifecycle_dashboard_is_provisionable_and_read_only() -> None:
    document = _dashboard()

    assert document["uid"] == "stageguard-lifecycle-safety"
    assert document["editable"] is False
    assert document["schemaVersion"] >= 39
    assert len({panel["id"] for panel in document["panels"]}) == len(document["panels"])
    assert all(panel["datasource"]["uid"] == "stageguard-prometheus" for panel in document["panels"])


def test_lifecycle_dashboard_uses_authoritative_runtime_state() -> None:
    expressions = _expressions(_dashboard())

    assert 'max(stageguard_lifecycle_safety_state{state!="ok"})' in expressions
    assert "stageguard_lifecycle_safety_state" in expressions
    assert any("timestamp(stageguard_lifecycle_safety_state)" in expression for expression in expressions)
    assert any("absent(stageguard_lifecycle_safety_state)" in expression for expression in expressions)


def test_lifecycle_dashboard_keeps_recovery_as_separate_proof() -> None:
    expressions = _expressions(_dashboard())

    assert "stageguard_recovery_verified" in expressions
    serialized = json.dumps(_dashboard()).lower()
    for forbidden in (
        "/approve",
        "/execute",
        "remediation_provider_token",
        "authorization: bearer",
        "curl ",
        "http method",
    ):
        assert forbidden not in serialized
