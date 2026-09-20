"""Regression tests for the local demo API process lifecycle.

These tests intentionally exercise only a process that was spawned by the current
call.  They must never discover or terminate arbitrary host PIDs.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("stageguard_demo_local", ROOT / "scripts" / "demo_local.py")
assert SPEC and SPEC.loader
DEMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEMO)


def _fake_process(*, poll_result=None):
    process = MagicMock()
    process.pid = 424242
    process.poll.return_value = poll_result
    return process


def test_spawn_api_removes_pid_file_when_child_exits_before_health(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"
    log_path = tmp_path / "stageguard-api.log"
    hmac_path = tmp_path / "checkpoint-hmac-key"
    process = _fake_process(poll_result=7)

    monkeypatch.setattr(DEMO, "PID_PATH", pid_path)
    monkeypatch.setattr(DEMO, "API_LOG", log_path)
    monkeypatch.setattr(DEMO, "HMAC_KEY_PATH", hmac_path)
    monkeypatch.setattr(DEMO, "STATE_DIR", tmp_path)
    monkeypatch.setattr(DEMO, "_api_running", lambda: False)
    monkeypatch.setattr(DEMO.subprocess, "Popen", lambda *args, **kwargs: process)

    with pytest.raises(DEMO.DemoError, match="exited with code 7"):
        DEMO._spawn_api(enable_gemini=False)

    assert not pid_path.exists(), "failed child startup must not leave a stale ownership PID file"


def test_spawn_api_timeout_terminates_only_the_process_it_spawned(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"
    log_path = tmp_path / "stageguard-api.log"
    hmac_path = tmp_path / "checkpoint-hmac-key"
    process = _fake_process(poll_result=None)
    ticks = iter((0.0, 31.0, 31.0))

    monkeypatch.setattr(DEMO, "PID_PATH", pid_path)
    monkeypatch.setattr(DEMO, "API_LOG", log_path)
    monkeypatch.setattr(DEMO, "HMAC_KEY_PATH", hmac_path)
    monkeypatch.setattr(DEMO, "STATE_DIR", tmp_path)
    monkeypatch.setattr(DEMO, "_api_running", lambda: False)
    monkeypatch.setattr(DEMO.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(DEMO.time, "monotonic", lambda: next(ticks))

    with pytest.raises(DEMO.DemoError, match="did not become healthy"):
        DEMO._spawn_api(enable_gemini=False)

    process.terminate.assert_called_once_with()
    process.wait.assert_called()
    assert not pid_path.exists(), "timed-out startup must clear the PID file after reaping its own child"


def test_reap_spawn_failure_escalates_to_kill_after_bounded_terminate_wait(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"
    pid_path.write_text("424242\n", encoding="utf-8")
    process = _fake_process(poll_result=None)
    process.wait.side_effect = [subprocess.TimeoutExpired(cmd="stageguard-api", timeout=5), 0]
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path)

    DEMO._reap_spawn_failure(process)

    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert process.wait.call_count == 2
    assert not pid_path.exists()


def test_reap_spawn_failure_fails_closed_if_owned_child_survives_kill(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"
    pid_path.write_text("424242\n", encoding="utf-8")
    process = _fake_process(poll_result=None)
    process.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="stageguard-api", timeout=5),
        subprocess.TimeoutExpired(cmd="stageguard-api", timeout=5),
    ]
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path)

    with pytest.raises(DEMO.DemoError, match="did not exit after terminate/kill"):
        DEMO._reap_spawn_failure(process)

    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert not pid_path.exists(), "failed cleanup must not retain misleading ownership metadata"
