from __future__ import annotations

from pathlib import Path

import pytest

from groundstation.dashboard.app import create_app


@pytest.fixture()
def app(tmp_path: Path):
    database_path = tmp_path / "orbitwatch.db"

    import groundstation.dashboard.routes as routes

    original_database = routes.DEFAULT_DATABASE
    routes.DEFAULT_DATABASE = database_path

    application = create_app(
        {
            "TESTING": True,
        }
    )

    yield application

    routes.DEFAULT_DATABASE = original_database


@pytest.fixture()
def client(app):
    return app.test_client()


def test_dashboard_index(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"ORBITWATCH" in response.data
    assert b"MISSION CONTROL" in response.data


def test_status_endpoint(client):
    response = client.get("/api/status")

    assert response.status_code == 200

    data = response.get_json()

    assert data["application"] == "OrbitWatch"
    assert data["status"] == "online"
    assert "timestamp" in data
    assert "sdr" in data
    assert "database" in data


def test_overview_endpoint(client):
    response = client.get("/api/overview")

    assert response.status_code == 200

    data = response.get_json()

    assert data["application"] == "OrbitWatch"
    assert data["status"] == "online"
    assert data["data_available"] is False
    assert data["statistics"]["packet_count"] == 0


def test_telemetry_endpoint(client):
    response = client.get("/api/telemetry")

    assert response.status_code == 200

    data = response.get_json()

    assert data["count"] == 0
    assert data["latest"] is None
    assert data["satellites"] == []


def test_history_endpoint(client):
    response = client.get("/api/telemetry/history")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data["history"], list)
    assert data["history"] == []


def test_sdr_endpoint(client):
    response = client.get("/api/sdr")

    assert response.status_code == 200

    data = response.get_json()

    assert "receiver" in data
    assert "devices" in data
    assert isinstance(data["devices"], list)


def test_mission_endpoint(client):
    response = client.get("/api/mission")

    assert response.status_code == 200

    data = response.get_json()

    assert "station" in data
    assert "satellites" in data
    assert "active_satellite" in data
    assert data["active_satellite"] is None


def test_health_endpoint(client):
    response = client.get("/api/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] in {"ok", "degraded"}
    assert "database" in data
    assert "timestamp" in data


def test_unknown_api_route(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
