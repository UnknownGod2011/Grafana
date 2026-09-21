from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


def _compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


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
    text = _compose_text()
    mcp_section = text.split("\n  mcp:\n", maxsplit=1)[1]

    assert "\n    ports:" not in mcp_section
