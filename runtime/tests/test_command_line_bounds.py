from __future__ import annotations

import pytest

from runtime.command_line import (
    MAX_LAUNCHER_ARGUMENT_CHARS,
    MAX_LAUNCHER_ARGUMENTS,
    MAX_LAUNCHER_COMMAND_CHARS,
    split_command,
)


def test_launcher_accepts_normal_stdio_command() -> None:
    assert split_command("mcp-grafana --transport stdio") == ["mcp-grafana", "--transport", "stdio"]


def test_launcher_rejects_oversized_raw_command_before_parsing() -> None:
    with pytest.raises(ValueError, match="maximum length"):
        split_command("x" * (MAX_LAUNCHER_COMMAND_CHARS + 1))


def test_launcher_rejects_excessive_argument_count() -> None:
    command = " ".join(["mcp-grafana", *(["x"] * MAX_LAUNCHER_ARGUMENTS)])
    assert len(command) <= MAX_LAUNCHER_COMMAND_CHARS
    with pytest.raises(ValueError, match="too many arguments"):
        split_command(command)


def test_launcher_rejects_oversized_individual_argument() -> None:
    command = "mcp-grafana " + ("x" * (MAX_LAUNCHER_ARGUMENT_CHARS + 1))
    assert len(command) <= MAX_LAUNCHER_COMMAND_CHARS
    with pytest.raises(ValueError, match="oversized argument"):
        split_command(command)


def test_launcher_accepts_argument_at_bound() -> None:
    argument = "x" * MAX_LAUNCHER_ARGUMENT_CHARS
    assert split_command(f"mcp-grafana {argument}") == ["mcp-grafana", argument]


@pytest.mark.parametrize("control", ["\x00", "\x01", "\t", "\n", "\r", "\x1f", "\x7f"])
def test_launcher_rejects_control_character_inside_quoted_argument(control: str) -> None:
    command = f'mcp-grafana "safe{control}unsafe"'
    with pytest.raises(ValueError, match="ASCII control characters"):
        split_command(command)


def test_launcher_allows_ordinary_space_inside_quoted_argument() -> None:
    assert split_command('mcp-grafana "safe value"') == ["mcp-grafana", "safe value"]


def test_windows_launcher_rejects_control_character_after_quote_normalization() -> None:
    with pytest.raises(ValueError, match="ASCII control characters"):
        split_command('"C:\\Tools\\mcp-grafana.exe" "safe\x7funsafe"', windows=True)


def test_launcher_still_rejects_network_transport_inside_bounds() -> None:
    with pytest.raises(ValueError, match="network transport is forbidden"):
        split_command("mcp-grafana --transport streamable-http")
