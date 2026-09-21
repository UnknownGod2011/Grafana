"""Regression gates for local demo teardown reporting.

A stop command must never report success after Docker Compose teardown failed. This
protects operators from assuming the observability stack was removed when owned
containers may still be running.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("stageguard_demo_local_stop", ROOT / "scripts" / "demo_local.py")
assert SPEC and SPEC.loader
DEMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEMO)


def test_stop_propagates_compose_down_failure_after_attempting_api_cleanup(monkeypatch):
    """An owned-stack teardown failure must be visible to callers, not swallowed."""
    stop_api = MagicMock()
    monkeypatch.setattr(DEMO, "_stop_api", stop_api)

    def fail_down(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=17, cmd=["docker", "compose", "down"])

    monkeypatch.setattr(DEMO, "_docker", fail_down)

    with pytest.raises(DEMO.DemoError, match="Docker Compose teardown failed"):
        DEMO.stop(keep_stack=False)

    stop_api.assert_called_once_with()


def test_stop_keep_stack_never_invokes_compose_down(monkeypatch):
    """Explicit keep-stack remains a safe escape hatch for operator-owned telemetry."""
    stop_api = MagicMock()
    docker = MagicMock()
    monkeypatch.setattr(DEMO, "_stop_api", stop_api)
    monkeypatch.setattr(DEMO, "_docker", docker)

    DEMO.stop(keep_stack=True)

    stop_api.assert_called_once_with()
    docker.assert_not_called()
