from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


def _compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def _service_section(name: str, next_name: str | None = None) -> str:
    text = _compose_text().split(f"\n  {name}:\n", maxsplit=1)[1]
    if next_name is not None:
        text = text.split(f"\n  {next_name}:\n", maxsplit=1)[0]
    return text


def _mcp_section() -> str:
    return _service_section("mcp")


def test_mcp_is_explicitly_opt_in_and_stdio_only() -> None:
    mcp = _mcp_section()
    assert 'profiles: ["mcp"]' in mcp
    assert "\n      - stdio\n" in mcp
    assert "\n    ports:" not in mcp


def test_mcp_tool_surface_remains_read_only_and_narrow() -> None:
    mcp = _mcp_section()
    assert "\n      - --disable-write\n" in mcp
    assert "\n      - --disable-proxied\n" in mcp
    assert "\n      - datasource,prometheus,loki\n" in mcp


def test_mcp_has_bounded_local_resources() -> None:
    mcp = _mcp_section()
    assert "\n    mem_limit: 256m\n" in mcp
    assert "\n    cpus: 0.50\n" in mcp
    assert "\n    pids_limit: 128\n" in mcp


def test_mcp_loki_result_limit_stays_bounded() -> None:
    mcp = _mcp_section()
    assert "\n      - --max-loki-log-limit\n      - \"8\"\n" in mcp


def test_mcp_waits_for_grafana_http_readiness() -> None:
    grafana = _service_section("grafana", "mcp")
    mcp = _mcp_section()

    assert "\n    healthcheck:\n" in grafana
    assert "http://localhost:3000/api/health" in grafana
    assert "\n      grafana:\n        condition: service_healthy\n" in mcp
