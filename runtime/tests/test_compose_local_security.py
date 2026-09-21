from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


def _compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def _mcp_section() -> str:
    return _compose_text().split("\n  mcp:\n", maxsplit=1)[1]


def test_local_host_ports_are_loopback_only() -> None:
    """Local fixtures must not regress to Docker's all-interface port publishing."""
    text = _compose_text()

    expected = {
        "127.0.0.1:9108:9108",  # simulator mutation API
        "127.0.0.1:9111:9111",  # watchdog fixture
        "127.0.0.1:9090:9090",  # unauthenticated Prometheus
        "127.0.0.1:3000:3000",  # demo-credential Grafana
    }
    published = set(
        re.findall(r'^\s*-\s*["\']([^"\']+:[^"\']+)["\']\s*$', text, re.MULTILINE)
    )

    assert expected <= published
    assert published == expected, (
        "Every host-published local service must be reviewed and explicitly bound "
        f"to loopback; found unexpected mappings: {sorted(published - expected)}"
    )
    assert all(mapping.startswith("127.0.0.1:") for mapping in published)


def test_mcp_has_no_host_port_publication() -> None:
    """The stdio MCP sidecar should remain reachable only through its process transport."""
    assert "\n    ports:" not in _mcp_section()


def test_mcp_container_is_least_privilege() -> None:
    """The read-only evidence adapter must not gain filesystem/capability mutation power."""
    mcp = _mcp_section()

    assert "\n    read_only: true\n" in mcp
    assert re.search(r"\n    cap_drop:\n\s+- ALL\n", mcp)
    assert re.search(r"\n    security_opt:\n\s+- no-new-privileges:true\n", mcp)


def test_mcp_token_is_file_backed_and_mounted_read_only() -> None:
    """Do not regress to an inline service-account token in Compose."""
    mcp = _mcp_section()

    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE: /run/secrets/grafana-mcp-token" in mcp
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN:" not in mcp
    assert "./runtime/.secrets/grafana-mcp-token:/run/secrets/grafana-mcp-token:ro" in mcp
