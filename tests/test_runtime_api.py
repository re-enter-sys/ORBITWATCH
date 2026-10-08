from __future__ import annotations

from pathlib import Path

import groundstation.runtime as runtime
from groundstation.dashboard.app import create_app
from groundstation.dashboard import routes


def test_mode_api_reports_idle(
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

    app = create_app(
        {
            "TESTING": True,
        }
    )

    client = app.test_client()

    response = client.get(
        "/api/mode"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["mode"] == "IDLE"
    assert payload["runtime"]["data_source"] == "NONE"


def test_mode_api_can_return_to_idle(
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
        session_id="test",
        satellite="OW-TEST",
    )

    app = create_app(
        {
            "TESTING": True,
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/mode",
        json={
            "mode": "IDLE",
        },
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["success"] is True
    assert payload["mode"] == "IDLE"


def test_dashboard_refuses_fake_live_mode(
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

    app = create_app(
        {
            "TESTING": True,
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/mode",
        json={
            "mode": "LIVE",
        },
    )

    assert response.status_code == 409

    payload = response.get_json()

    assert payload["success"] is False
    assert payload["mode"] == "IDLE"


def test_dashboard_can_start_replay_mode(
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

    class DummyProcess:
        pid = 12345

    def fake_popen(*args, **kwargs):
        return DummyProcess()

    monkeypatch.setattr(
        routes.subprocess,
        "Popen",
        fake_popen,
    )

    app = create_app(
        {
            "TESTING": True,
        }
    )

    client = app.test_client()

    response = client.post(
        "/api/mode",
        json={
            "mode": "REPLAY",
        },
    )

    assert response.status_code == 202

    payload = response.get_json()

    assert payload["success"] is True
    assert payload["starting"] is True
    assert payload["mode"] == "REPLAY"

    state = runtime.read_runtime_state()

    assert state.mode == "REPLAY"
    assert state.data_source == "REPLAY"
    assert state.satellite == "OW-DEMO"
    assert state.status == "running"
