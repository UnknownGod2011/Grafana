"""Regression gates for local demo teardown reporting.

A stop command must never report success after Docker Compose teardown failed, and
must independently attempt each cleanup component it owns. This protects operators
from assuming cleanup completed when the API or observability containers may still
be running.
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


def test_stop_missing_docker_is_reported_as_partial_cleanup(monkeypatch):
    """A missing Docker executable is a teardown failure, not successful stop."""
    stop_api = MagicMock()
    monkeypatch.setattr(DEMO, "_stop_api", stop_api)

    def missing_docker(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(DEMO, "_docker", missing_docker)

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


def test_stop_attempts_compose_cleanup_even_when_api_cleanup_fails(monkeypatch):
    """One cleanup failure must not prevent an independent owned component cleanup."""
    docker = MagicMock()

    def fail_api_stop():
        raise DEMO.DemoError("verified StageGuard API did not stop")

    monkeypatch.setattr(DEMO, "_stop_api", fail_api_stop)
    monkeypatch.setattr(DEMO, "_docker", docker)

    with pytest.raises(DEMO.DemoError, match="StageGuard API"):
        DEMO.stop(keep_stack=False)

    docker.assert_called_once_with("down")


def test_stop_aggregates_api_and_compose_failures(monkeypatch):
    """Operators must see both failures when neither owned component cleaned up."""
    def fail_api_stop():
        raise DEMO.DemoError("verified StageGuard API did not stop")

    def fail_down(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=23, cmd=["docker", "compose", "down"])

    monkeypatch.setattr(DEMO, "_stop_api", fail_api_stop)
    monkeypatch.setattr(DEMO, "_docker", fail_down)

    with pytest.raises(DEMO.DemoError) as exc_info:
        DEMO.stop(keep_stack=False)

    message = str(exc_info.value)
    assert "StageGuard API" in message
    assert "Docker Compose" in message


def test_stop_verifies_compose_has_no_remaining_containers(monkeypatch):
    """A zero exit from `compose down` is not sufficient if owned containers remain."""
    stop_api = MagicMock()
    calls = []

    def docker(*args, **kwargs):
        calls.append((args, kwargs))
        if args == ("down",):
            return MagicMock(returncode=0, stdout="")
        if args == ("ps", "-q"):
            return MagicMock(returncode=0, stdout="stageguard-grafana-container-id\n")
        raise AssertionError(f"unexpected docker invocation: {args}")

    monkeypatch.setattr(DEMO, "_stop_api", stop_api)
    monkeypatch.setattr(DEMO, "_docker", docker)

    with pytest.raises(DEMO.DemoError, match="still has running or retained containers"):
        DEMO.stop(keep_stack=False)

    stop_api.assert_called_once_with()
    assert calls == [
        (("down",), {}),
        (("ps", "-q"), {"capture": True}),
    ]


def test_stop_accepts_verified_empty_compose_project(monkeypatch):
    """Successful cleanup requires both `down` and an empty project-container query."""
    stop_api = MagicMock()
    calls = []

    def docker(*args, **kwargs):
        calls.append((args, kwargs))
        if args == ("down",):
            return MagicMock(returncode=0, stdout="")
        if args == ("ps", "-q"):
            return MagicMock(returncode=0, stdout="")
        raise AssertionError(f"unexpected docker invocation: {args}")

    monkeypatch.setattr(DEMO, "_stop_api", stop_api)
    monkeypatch.setattr(DEMO, "_docker", docker)

    DEMO.stop(keep_stack=False)

    stop_api.assert_called_once_with()
    assert calls == [
        (("down",), {}),
        (("ps", "-q"), {"capture": True}),
    ]
