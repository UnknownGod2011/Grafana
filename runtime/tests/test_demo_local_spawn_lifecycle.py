"""Regression tests for the local demo API process lifecycle.

These tests intentionally constrain termination authority. Startup cleanup may only
act on the exact child it spawned; persistent PID shutdown must verify process
identity before signalling anything.
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
    pid_path = tmp_path / "stageguard-api.pid"; log_path = tmp_path / "stageguard-api.log"; hmac_path = tmp_path / "checkpoint-hmac-key"
    process = _fake_process(poll_result=7)
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path); monkeypatch.setattr(DEMO, "API_LOG", log_path); monkeypatch.setattr(DEMO, "HMAC_KEY_PATH", hmac_path); monkeypatch.setattr(DEMO, "STATE_DIR", tmp_path)
    monkeypatch.setattr(DEMO, "_api_running", lambda: False); monkeypatch.setattr(DEMO.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(DEMO.DemoError, match="exited with code 7"): DEMO._spawn_api(enable_gemini=False)
    assert not pid_path.exists()


def test_spawn_api_timeout_terminates_only_the_process_it_spawned(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"; log_path = tmp_path / "stageguard-api.log"; hmac_path = tmp_path / "checkpoint-hmac-key"
    process = _fake_process(poll_result=None); ticks = iter((0.0, 31.0, 31.0))
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path); monkeypatch.setattr(DEMO, "API_LOG", log_path); monkeypatch.setattr(DEMO, "HMAC_KEY_PATH", hmac_path); monkeypatch.setattr(DEMO, "STATE_DIR", tmp_path)
    monkeypatch.setattr(DEMO, "_api_running", lambda: False); monkeypatch.setattr(DEMO.subprocess, "Popen", lambda *args, **kwargs: process); monkeypatch.setattr(DEMO.time, "monotonic", lambda: next(ticks))
    with pytest.raises(DEMO.DemoError, match="did not become healthy"): DEMO._spawn_api(enable_gemini=False)
    process.terminate.assert_called_once_with(); process.wait.assert_called(); assert not pid_path.exists()


def test_reap_spawn_failure_escalates_to_kill_after_bounded_terminate_wait(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"; pid_path.write_text("424242\n", encoding="utf-8")
    process = _fake_process(poll_result=None); process.wait.side_effect = [subprocess.TimeoutExpired(cmd="stageguard-api", timeout=5), 0]
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path); DEMO._reap_spawn_failure(process)
    process.terminate.assert_called_once_with(); process.kill.assert_called_once_with(); assert process.wait.call_count == 2; assert not pid_path.exists()


def test_reap_spawn_failure_fails_closed_if_owned_child_survives_kill(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"; pid_path.write_text("424242\n", encoding="utf-8")
    process = _fake_process(poll_result=None); process.wait.side_effect = [subprocess.TimeoutExpired(cmd="stageguard-api", timeout=5), subprocess.TimeoutExpired(cmd="stageguard-api", timeout=5)]
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path)
    with pytest.raises(DEMO.DemoError, match="did not exit after terminate/kill"): DEMO._reap_spawn_failure(process)
    process.terminate.assert_called_once_with(); process.kill.assert_called_once_with(); assert not pid_path.exists()


def test_stop_api_refuses_to_signal_unverified_reused_pid(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"; pid_path.write_text("424242\n", encoding="utf-8")
    kill = MagicMock()
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path); monkeypatch.setattr(DEMO, "_api_running", lambda: True); monkeypatch.setattr(DEMO, "_pid_matches_stageguard_api", lambda pid: False); monkeypatch.setattr(DEMO.os, "kill", kill)
    with pytest.raises(DEMO.DemoError, match="refusing to signal"): DEMO._stop_api()
    kill.assert_not_called(); assert pid_path.exists(), "uncertain ownership metadata must be retained for operator inspection"


def test_stop_api_signals_only_verified_stageguard_pid_and_clears_metadata(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"; pid_path.write_text("424242\n", encoding="utf-8")
    states = iter((True, False, False)); kill = MagicMock()
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path); monkeypatch.setattr(DEMO, "_api_running", lambda: next(states)); monkeypatch.setattr(DEMO, "_pid_matches_stageguard_api", lambda pid: pid == 424242); monkeypatch.setattr(DEMO.os, "kill", kill)
    DEMO._stop_api()
    kill.assert_called_once_with(424242, DEMO.signal.SIGTERM); assert not pid_path.exists()


def test_stop_api_retains_metadata_when_verified_process_does_not_stop(monkeypatch, tmp_path):
    pid_path = tmp_path / "stageguard-api.pid"; pid_path.write_text("424242\n", encoding="utf-8")
    ticks = iter((0.0, 6.0)); kill = MagicMock()
    monkeypatch.setattr(DEMO, "PID_PATH", pid_path); monkeypatch.setattr(DEMO, "_api_running", lambda: True); monkeypatch.setattr(DEMO, "_pid_matches_stageguard_api", lambda pid: True); monkeypatch.setattr(DEMO.os, "kill", kill); monkeypatch.setattr(DEMO.time, "monotonic", lambda: next(ticks))
    with pytest.raises(DEMO.DemoError, match="did not stop after SIGTERM"): DEMO._stop_api()
    kill.assert_called_once(); assert pid_path.exists(), "failed shutdown must retain ownership metadata for safe follow-up"


def test_pid_identity_requires_full_local_stageguard_signature(monkeypatch):
    monkeypatch.setattr(DEMO, "_pid_command", lambda pid: "python /tmp/runtime/bootstrap.py --identity-mode local --port 9110")
    assert DEMO._pid_matches_stageguard_api(7)
    monkeypatch.setattr(DEMO, "_pid_command", lambda pid: "python innocent.py --port 9110")
    assert not DEMO._pid_matches_stageguard_api(7)
