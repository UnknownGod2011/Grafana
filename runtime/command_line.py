#!/usr/bin/env python3
"""Cross-platform command-line parsing for StageGuard child-process launchers.

StageGuard accepts launcher commands through environment variables so operators can
use Docker, a native mcp-grafana binary, or a Python wrapper. POSIX ``shlex`` is not
safe for unescaped Windows paths such as ``C:\\Tools\\mcp-grafana.exe`` because the
backslashes are treated as escape characters. Keep that platform distinction in one
small helper rather than duplicating parser behavior across adapters.

The same boundary also enforces StageGuard's local stdio-only MCP transport policy.
The official mcp-grafana binary defaults to stdio, while its Docker image defaults to
a network transport. StageGuard must never turn an evidence-plane launcher override
into an unauthenticated/listening MCP server by accident.
"""
from __future__ import annotations

import os
import shlex


_MCP_TRANSPORT_FLAGS = frozenset({"-t", "--transport"})
_MCP_NETWORK_TRANSPORTS = frozenset({"sse", "streamable-http"})
_OFFICIAL_MCP_DOCKER_IMAGE = "grafana/mcp-grafana"
_DOCKER_HUB_REGISTRY_PREFIXES = (
    "docker.io/",
    "index.docker.io/",
    "registry-1.docker.io/",
)
# Characters that can alter terminal/log rendering without being ordinary printable
# launcher text. C0/DEL/C1 cover terminal controls; the Unicode set covers explicit
# line separators and bidi embedding/override/isolate marks commonly involved in
# diagnostic spoofing. Normal non-ASCII executable paths and arguments remain valid.
_UNICODE_DIAGNOSTIC_CONTROLS = frozenset(
    {
        0x2028,  # LINE SEPARATOR
        0x2029,  # PARAGRAPH SEPARATOR
        0x202A,  # LEFT-TO-RIGHT EMBEDDING
        0x202B,  # RIGHT-TO-LEFT EMBEDDING
        0x202C,  # POP DIRECTIONAL FORMATTING
        0x202D,  # LEFT-TO-RIGHT OVERRIDE
        0x202E,  # RIGHT-TO-LEFT OVERRIDE
        0x2066,  # LEFT-TO-RIGHT ISOLATE
        0x2067,  # RIGHT-TO-LEFT ISOLATE
        0x2068,  # FIRST STRONG ISOLATE
        0x2069,  # POP DIRECTIONAL ISOLATE
    }
)
MAX_LAUNCHER_COMMAND_CHARS = 8192
MAX_LAUNCHER_ARGUMENTS = 128
MAX_LAUNCHER_ARGUMENT_CHARS = 2048


def _transport_values(parts: list[str]) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part in _MCP_TRANSPORT_FLAGS:
            if index + 1 >= len(parts):
                raise ValueError("MCP transport flag requires a value")
            values.append(parts[index + 1].strip().lower())
            index += 2
            continue
        for prefix in ("-t=", "--transport="):
            if part.startswith(prefix):
                values.append(part[len(prefix) :].strip().lower())
                break
        index += 1
    return values


def _is_official_mcp_docker_image(part: str) -> bool:
    """Recognize the official image with or without Docker Hub registry aliases.

    Docker accepts both the familiar ``grafana/mcp-grafana`` spelling and explicit
    Docker Hub registry-qualified forms. Treat them identically so adding a registry
    prefix cannot bypass StageGuard's requirement to opt the image into stdio.
    Other registries are deliberately not assumed to host the official image.
    """
    normalized = part.strip().lower()
    for prefix in _DOCKER_HUB_REGISTRY_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized == _OFFICIAL_MCP_DOCKER_IMAGE or normalized.startswith(
        _OFFICIAL_MCP_DOCKER_IMAGE + ":"
    ) or normalized.startswith(_OFFICIAL_MCP_DOCKER_IMAGE + "@")


def _contains_diagnostic_control(value: str) -> bool:
    """Return whether argv text contains a control that can corrupt diagnostics.

    Launcher configuration is operator-controlled, but rejecting terminal controls,
    Unicode line separators, and bidi formatting controls here makes errors/logs
    deterministic before subprocess creation. Ordinary spaces and printable Unicode
    (including non-ASCII filesystem paths) remain supported.
    """
    for char in value:
        codepoint = ord(char)
        if codepoint < 0x20 or 0x7F <= codepoint <= 0x9F:
            return True
        if codepoint in _UNICODE_DIAGNOSTIC_CONTROLS:
            return True
    return False


def _enforce_stdio_mcp_transport(parts: list[str]) -> None:
    transports = _transport_values(parts)
    if len(transports) > 1:
        raise ValueError("MCP launcher must declare transport at most once")
    if transports and transports[0] != "stdio":
        if transports[0] in _MCP_NETWORK_TRANSPORTS:
            raise ValueError("StageGuard requires Grafana MCP stdio transport; network transport is forbidden")
        raise ValueError("StageGuard requires Grafana MCP stdio transport")

    # mcp-grafana's native binary defaults to stdio, but the official Docker
    # image defaults to a network transport. A direct `docker run` therefore
    # has to opt into stdio explicitly. `docker compose run ... mcp` is allowed
    # because the repository service itself pins `-t stdio` in compose config.
    if any(_is_official_mcp_docker_image(part) for part in parts) and transports != ["stdio"]:
        raise ValueError("direct grafana/mcp-grafana Docker launch must explicitly set -t stdio")


def split_command(command: str, *, windows: bool | None = None) -> list[str]:
    """Split and validate a configured MCP launcher command.

    ``shlex`` has no exact ``CommandLineToArgvW`` mode, but ``posix=False`` preserves
    backslashes and quoted groups, which is sufficient for StageGuard's launcher
    configuration. It also leaves surrounding quotes on quoted tokens, so strip one
    matching quote pair before passing argv directly to ``subprocess.Popen``.

    Explicit SSE/streamable-HTTP transports are rejected. Direct use of the
    official Docker image must also declare ``-t stdio`` because that image's
    default transport differs from the native binary's default.

    Launcher text, argument count, individual argument size, and diagnostic control
    characters are bounded before subprocess creation so an accidentally corrupted
    environment cannot turn this release-smoke boundary into pathological parser/argv
    work or ambiguous/spoofed diagnostics.

    ``windows`` is injectable for deterministic cross-platform tests.
    """
    if not isinstance(command, str) or not command.strip():
        raise ValueError("launcher command must be non-empty")
    if len(command) > MAX_LAUNCHER_COMMAND_CHARS:
        raise ValueError("launcher command exceeds maximum length")

    is_windows = os.name == "nt" if windows is None else bool(windows)
    try:
        parts = shlex.split(command, posix=not is_windows)
    except ValueError as exc:
        raise ValueError("launcher command has invalid quoting") from exc

    if is_windows:
        normalized: list[str] = []
        for part in parts:
            if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"}:
                part = part[1:-1]
            normalized.append(part)
        parts = normalized

    if not parts or any(part == "" for part in parts):
        raise ValueError("launcher command must contain non-empty arguments")
    if len(parts) > MAX_LAUNCHER_ARGUMENTS:
        raise ValueError("launcher command contains too many arguments")
    if any(len(part) > MAX_LAUNCHER_ARGUMENT_CHARS for part in parts):
        raise ValueError("launcher command contains an oversized argument")
    if any(_contains_diagnostic_control(part) for part in parts):
        raise ValueError("launcher command contains an argument with diagnostic control characters")

    _enforce_stdio_mcp_transport(parts)
    return parts
