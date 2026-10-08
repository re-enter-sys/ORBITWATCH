from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from groundstation.mission.service import MissionLogService
from groundstation.simulation.mission import run_demo
from groundstation.simulation.samples import (
    DEMO_SATELLITE,
    build_demo_events,
)


def test_demo_samples_are_real_kiss_ax25_packets():
    events = build_demo_events()

    assert len(events) == 3

    for index, event in enumerate(events, start=1):
        assert event.event_type == "KISS_FRAME"
        assert event.payload["mode"] == "REPLAY"
        assert event.payload["development"] is True
        assert event.payload["satellite"] == DEMO_SATELLITE
        assert event.payload["packet_sequence"] == index

        encoded = event.payload["kiss_hex"]

        assert isinstance(encoded, str)
        assert encoded

        raw = bytes.fromhex(encoded)

        assert raw[0] == 0xC0
        assert raw[-1] == 0xC0


def test_demo_run_creates_recording_and_databases(tmp_path: Path):
    data_root = tmp_path / "data"

    result = run_demo(
        data_root=data_root,
        speed=100.0,
        realtime=False,
    )

    assert result["mode"] == "REPLAY"
    assert result["development"] is True
    assert result["satellite"] == DEMO_SATELLITE

    assert result["packets_processed"] == 3
    assert result["packets_decoded"] == 3
    assert result["packets_failed"] == 0

    assert (
        result["replay"]["state"]
        == "completed"
    )

    assert Path(
        result["recording"]
    ).exists()

    assert Path(
        result["telemetry_database"]
    ).exists()

    assert Path(
        result["mission_database"]
    ).exists()


def test_demo_persists_telemetry(tmp_path: Path):
    data_root = tmp_path / "data"

    result = run_demo(
        data_root=data_root,
        speed=100.0,
    )

    connection = sqlite3.connect(
        result["telemetry_database"]
    )

    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM telemetry_records"
        ).fetchone()[0]

        assert count == 3

        satellites = connection.execute(
            """
            SELECT DISTINCT satellite
            FROM telemetry_records
            """
        ).fetchall()

        assert satellites == [
            (DEMO_SATELLITE,),
        ]

        rows = connection.execute(
            """
            SELECT
                satellite,
                source,
                packet_id,
                valid
            FROM telemetry_records
            ORDER BY id
            """
        ).fetchall()

        assert len(rows) == 3

        for satellite, source, packet_id, valid in rows:
            assert satellite == DEMO_SATELLITE
            assert source == "replay"
            assert packet_id.startswith("events-")
            assert valid == 1

    finally:
        connection.close()


def test_demo_persists_mission_events(tmp_path: Path):
    data_root = tmp_path / "data"

    result = run_demo(
        data_root=data_root,
        speed=100.0,
    )

    mission_service = MissionLogService(
        result["mission_database"]
    )

    try:
        events = mission_service.events(
            limit=100
        )

        event_types = [
            event.event_type.value
            for event in events
        ]

        assert "mission_started" in event_types
        assert "replay_started" in event_types
        assert "packet_received" in event_types
        assert "telemetry_received" in event_types
        assert "replay_completed" in event_types
        assert "mission_stopped" in event_types

        packet_events = [
            event
            for event in events
            if event.event_type.value
            == "packet_received"
        ]

        telemetry_events = [
            event
            for event in events
            if event.event_type.value
            == "telemetry_received"
        ]

        assert len(packet_events) == 3
        assert len(telemetry_events) == 3

        for event in telemetry_events:
            assert event.satellite == DEMO_SATELLITE
            assert event.payload.get(
                "development"
            ) is True

    finally:
        mission_service.close()


def test_demo_is_append_safe(tmp_path: Path):
    data_root = tmp_path / "data"

    first = run_demo(
        data_root=data_root,
        speed=100.0,
    )

    second = run_demo(
        data_root=data_root,
        speed=100.0,
    )

    assert first["packets_decoded"] == 3
    assert second["packets_decoded"] == 3

    connection = sqlite3.connect(
        second["telemetry_database"]
    )

    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM telemetry_records"
        ).fetchone()[0]

        assert count == 6

    finally:
        connection.close()
