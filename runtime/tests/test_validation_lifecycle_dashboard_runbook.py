import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "runtime" / "grafana" / "dashboards" / "stageguard-lifecycle.json"
RUNBOOK = ROOT / "docs" / "runbooks" / "lifecycle-safety.md"
EXPECTED_URL = (
    "https://github.com/UnknownGod2011/Grafana/blob/main/"
    "docs/runbooks/lifecycle-safety.md"
)


def test_lifecycle_dashboard_links_to_repository_owned_runbook() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    links = dashboard.get("links", [])
    runbook_links = [link for link in links if link.get("url") == EXPECTED_URL]

    assert RUNBOOK.is_file(), "dashboard must not point at a missing operator runbook"
    assert len(runbook_links) == 1
    link = runbook_links[0]
    assert link.get("type") == "link"
    assert link.get("targetBlank") is True
    assert "runbook" in link.get("title", "").lower()


def test_lifecycle_dashboard_remains_read_only_observability() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    serialized = json.dumps(dashboard).lower()

    assert dashboard.get("editable") is False
    assert "stageguard_lifecycle_safety_state" in serialized
    assert "stageguard_recovery_verified" in serialized

    # Dashboard navigation must never become a remediation/control surface.
    forbidden = (
        "/approve",
        "/execute",
        "authorization: bearer",
        "provider_api_key",
        "remediation_token",
    )
    for marker in forbidden:
        assert marker not in serialized
