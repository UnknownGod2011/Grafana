#!/usr/bin/env python3
"""Cross-platform command-line parsing for StageGuard child-process launchers.

StageGuard accepts launcher commands through environment variables so operators can
use Docker, a native mcp-grafana binary, or a Python wrapper. POSIX ``shlex`` is not
safe for unescaped Windows paths such as ``C:\\Tools\\mcp-grafana.exe`` because the
backslashes are treated as escape characters. Keep that platform distinction in one
small helper rather than duplicating parser behavior across adapters.
"""
from __future__ import annotations

import os
import shlex


def split_command(command: str, *, windows: bool | None = None) -> list[str]:
    """Split a configured launcher command without corrupting Windows paths.

    ``shlex`` has no exact ``CommandLineToArgvW`` mode, but ``posix=False`` preserves
    backslashes and quoted groups, which is sufficient for StageGuard's launcher
    configuration. It also leaves surrounding quotes on quoted tokens, so strip one
    matching quote pair before passing argv directly to ``subprocess.Popen``.

    ``windows`` is injectable for deterministic cross-platform tests.
    """
    if not isinstance(command, str) or not command.strip():
        raise ValueError("launcher command must be non-empty")

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
    return parts
