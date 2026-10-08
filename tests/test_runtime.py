from __future__ import annotations

import json
from pathlib import Path

import groundstation.runtime as runtime


def test_default_runtime_state_is_idle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_file = tmp_path / "state.json"
    runtime_directory = tmp_path

    monkeypatch.setattr(
        runtime,
        "STATE_FILE",
        state_file,
    )

    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORY",
        runtime_directory,
    )

    state = runtime.read_runtime_state()

    assert state.mode == "IDLE"
    assert state.data_source == "NONE"
    assert state.status == "idle"


def test_set_replay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_file = tmp_path / "state.json"

    monkeypatch.setattr(
        runtime,
        "STATE_FILE",
        state_file,
    )

    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORY",
        tmp_path,
    )

    state = runtime.set_replay(
        session_id="test-session",
        satellite="OW-TEST",
    )

    assert state.mode == "REPLAY"
    assert state.data_source == "REPLAY"
    assert state.status == "running"
    assert state.session_id == "test-session"
    assert state.satellite == "OW-TEST"


def test_set_idle_clears_previous_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_file = tmp_path / "state.json"

    monkeypatch.setattr(
        runtime,
        "STATE_FILE",
        state_file,
    )

    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORY",
        tmp_path,
    )

    runtime.set_replay(
        session_id="session-1",
        satellite="OW-TEST",
    )

    state = runtime.set_idle()

    assert state.mode == "IDLE"
    assert state.session_id is None
    assert state.satellite is None
    assert state.data_source == "NONE"
    assert state.status == "idle"


def test_runtime_state_is_persisted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_file = tmp_path / "state.json"

    monkeypatch.setattr(
        runtime,
        "STATE_FILE",
        state_file,
    )

    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORY",
        tmp_path,
    )

    runtime.set_replay(
        session_id="persisted",
        satellite="OW-TEST",
    )

    assert state_file.exists()

    payload = json.loads(
        state_file.read_text(
            encoding="utf-8"
        )
    )

    assert payload["mode"] == "REPLAY"
    assert payload["session_id"] == "persisted"

    loaded = runtime.read_runtime_state()

    assert loaded.mode == "REPLAY"
    assert loaded.session_id == "persisted"


def test_runtime_state_does_not_depend_on_telemetry_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_file = tmp_path / "state.json"

    monkeypatch.setattr(
        runtime,
        "STATE_FILE",
        state_file,
    )

    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORY",
        tmp_path,
    )

    runtime.set_idle()

    # This test deliberately does not create or inspect a telemetry DB.
    # Runtime mode is independent of historical telemetry records.
    state = runtime.read_runtime_state()

    assert state.mode == "IDLE"
