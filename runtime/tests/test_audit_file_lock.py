from __future__ import annotations

import threading
from types import SimpleNamespace

import retention_coordinator
from anchored_incident_service import AnchoredJsonlAuditLog
from audit_file_lock import audit_file_lock, lock_path_for
from incident_service import AuditEvent


def _event(sequence: int = 1) -> AuditEvent:
    return AuditEvent(
        sequence=sequence,
        timestamp_unix_ms=sequence,
        incident_id="incident-lock",
        event_type="test",
        actor="test",
        payload={},
    )


def test_anchored_jsonl_append_waits_for_cooperative_lock(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(path)
    started = threading.Event()
    finished = threading.Event()

    def writer() -> None:
        started.set()
        audit.append(_event())
        finished.set()

    with audit_file_lock(path):
        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        assert started.wait(1)
        assert not finished.wait(0.05)

    assert finished.wait(1)
    thread.join(timeout=1)
    assert audit.read(incident_id="incident-lock") == [_event()]
    assert lock_path_for(path).exists()


def test_anchored_jsonl_read_waits_for_cooperative_lock(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(path)
    audit.append(_event())
    started = threading.Event()
    finished = threading.Event()

    def reader() -> None:
        started.set()
        assert audit.read_candidates(incident_id="incident-lock", through_sequence=1) == [_event()]
        finished.set()

    with audit_file_lock(path):
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        assert started.wait(1)
        assert not finished.wait(0.05)

    assert finished.wait(1)
    thread.join(timeout=1)


def test_coordinated_execute_holds_lock_around_underlying_executor(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(path)
    entered_executor = threading.Event()
    release_executor = threading.Event()
    append_finished = threading.Event()
    result = object()

    monkeypatch.setattr(
        retention_coordinator,
        "parse_signed_plan_document",
        lambda document, signing_key: SimpleNamespace(audit_path=str(path)),
    )

    def fake_execute(*args, **kwargs):
        entered_executor.set()
        assert release_executor.wait(1)
        return result

    monkeypatch.setattr(retention_coordinator, "execute_local_retention", fake_execute)

    holder: list[object] = []

    def execute() -> None:
        holder.append(
            retention_coordinator.coordinated_execute_local_retention(
                {"plan": "fake"},
                object(),
                signing_key=b"x" * 32,
            )
        )

    execute_thread = threading.Thread(target=execute, daemon=True)
    execute_thread.start()
    assert entered_executor.wait(1)

    append_thread = threading.Thread(
        target=lambda: (audit.append(_event()), append_finished.set()),
        daemon=True,
    )
    append_thread.start()
    assert not append_finished.wait(0.05)

    release_executor.set()
    execute_thread.join(timeout=1)
    assert holder == [result]
    assert append_finished.wait(1)
    append_thread.join(timeout=1)
    assert audit.read(incident_id="incident-lock") == [_event()]


def test_coordinated_prepare_holds_lock_around_full_plan_preparation(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(path)
    entered_prepare = threading.Event()
    release_prepare = threading.Event()
    append_finished = threading.Event()
    document = {"signed": True}

    def fake_prepare(*args, **kwargs):
        entered_prepare.set()
        assert release_prepare.wait(1)
        return document

    monkeypatch.setattr(retention_coordinator, "prepare_local_retention_plan", fake_prepare)

    holder: list[dict[str, object]] = []

    def prepare() -> None:
        holder.append(
            retention_coordinator.coordinated_prepare_local_retention_plan(
                object(),
                path,
                signing_key=b"x" * 32,
                audit_integrity_state="verified",
            )
        )

    prepare_thread = threading.Thread(target=prepare, daemon=True)
    prepare_thread.start()
    assert entered_prepare.wait(1)

    append_thread = threading.Thread(
        target=lambda: (audit.append(_event()), append_finished.set()),
        daemon=True,
    )
    append_thread.start()
    assert not append_finished.wait(0.05)

    release_prepare.set()
    prepare_thread.join(timeout=1)
    assert holder == [document]
    assert append_finished.wait(1)
    append_thread.join(timeout=1)
