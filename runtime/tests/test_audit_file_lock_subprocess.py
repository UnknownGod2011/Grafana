from __future__ import annotations

import multiprocessing
from pathlib import Path

from anchored_incident_service import AnchoredJsonlAuditLog
from audit_file_lock import audit_file_lock, lock_path_for
from incident_service import AuditEvent


def _event(sequence: int = 1) -> AuditEvent:
    return AuditEvent(
        sequence=sequence,
        timestamp_unix_ms=sequence,
        incident_id="incident-subprocess-lock",
        event_type="test",
        actor="test",
        payload={},
    )


def _hold_audit_lock(path: str, acquired, release) -> None:
    with audit_file_lock(path):
        acquired.set()
        if not release.wait(10):
            raise RuntimeError("parent did not release subprocess audit lock")


def _append_event(path: str, started, finished) -> None:
    started.set()
    AnchoredJsonlAuditLog(Path(path)).append(_event())
    finished.set()


def test_audit_lock_excludes_writer_across_spawned_processes(tmp_path):
    """The sidecar lock must coordinate independent OS processes, not just threads."""
    path = tmp_path / "audit.jsonl"
    ctx = multiprocessing.get_context("spawn")
    acquired = ctx.Event()
    release = ctx.Event()
    writer_started = ctx.Event()
    writer_finished = ctx.Event()

    holder = ctx.Process(
        target=_hold_audit_lock,
        args=(str(path), acquired, release),
    )
    holder.start()
    try:
        assert acquired.wait(5), "lock-holder process did not acquire the audit lock"

        writer = ctx.Process(
            target=_append_event,
            args=(str(path), writer_started, writer_finished),
        )
        writer.start()
        try:
            assert writer_started.wait(5), "writer process did not start"
            assert not writer_finished.wait(0.2), (
                "writer crossed the audit lock while another process held it"
            )

            release.set()
            assert writer_finished.wait(5), "writer did not continue after lock release"
            writer.join(timeout=5)
            assert writer.exitcode == 0
        finally:
            if writer.is_alive():
                writer.terminate()
                writer.join(timeout=5)
    finally:
        release.set()
        holder.join(timeout=5)
        if holder.is_alive():
            holder.terminate()
            holder.join(timeout=5)

    assert holder.exitcode == 0
    audit = AnchoredJsonlAuditLog(path)
    assert audit.read(incident_id="incident-subprocess-lock") == [_event()]
    assert lock_path_for(path).exists()
