from __future__ import annotations

from groundstation.mission import (
    MissionEventSeverity,
    MissionEventType,
    MissionLogDatabase,
    MissionLogService,
    MissionLogger,
)


def test_database_creates_schema(tmp_path):
    path = tmp_path / "mission.db"

    database = MissionLogDatabase(path)

    assert path.exists()
    assert database.count() == 0

    database.close()


def test_start_and_stop_mission(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    session = service.start_mission(
        mode="replay",
        satellite="TEST-SAT",
    )

    assert session.mission_id.startswith("mission-")
    assert session.mode == "replay"
    assert session.satellite == "TEST-SAT"
    assert session.active is True

    stopped = service.stop_mission()

    assert stopped.active is False
    assert stopped.ended_at is not None

    service.close()


def test_mission_event_is_persisted(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live",
        satellite="TEST-SAT",
    )

    event = service.logger.satellite_acquired(
        "TEST-SAT"
    )

    assert event.event_type == MissionEventType.SATELLITE_ACQUIRED
    assert event.severity == MissionEventSeverity.SUCCESS

    events = service.events()

    assert len(events) == 2
    assert events[0].event_type == MissionEventType.SATELLITE_ACQUIRED

    service.close()


def test_packet_event(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="replay",
        satellite="TEST-SAT",
    )

    event = service.logger.packet_received(
        packet_id="PKT-001",
        satellite="TEST-SAT",
        protocol="AX.25",
        payload={
            "frame_length": 42,
        },
    )

    assert event.packet_id == "PKT-001"
    assert event.payload["protocol"] == "AX.25"

    events = service.events(
        event_type=MissionEventType.PACKET_RECEIVED
    )

    assert len(events) == 1
    assert events[0].packet_id == "PKT-001"

    service.close()


def test_telemetry_event(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="replay",
        satellite="TEST-SAT",
    )

    service.logger.telemetry_received(
        satellite="TEST-SAT",
        packet_id="PKT-001",
        payload={
            "temperature_c": 22.4,
            "voltage_v": 3.72,
        },
    )

    statistics = service.statistics()

    assert statistics.telemetry_events == 1
    assert statistics.total_events == 2

    service.close()


def test_crc_error_is_error(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    service.logger.crc_error(
        packet_id="PKT-BAD"
    )

    statistics = service.statistics()

    assert statistics.crc_errors == 1
    assert statistics.error_events == 1

    service.close()


def test_recording_and_replay_events(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="replay"
    )

    service.logger.recording_started(
        "iq-test-001"
    )

    service.logger.recording_stopped(
        "iq-test-001"
    )

    service.logger.replay_started(
        "iq-test-001"
    )

    service.logger.replay_paused(
        "iq-test-001"
    )

    service.logger.replay_resumed(
        "iq-test-001"
    )

    service.logger.replay_completed(
        "iq-test-001"
    )

    statistics = service.statistics()

    assert statistics.recordings_started == 1
    assert statistics.replays_completed == 1

    events = service.search("iq-test-001")

    assert len(events) == 6

    service.close()


def test_search_mission_events(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live",
        satellite="NOAA-TEST",
    )

    service.logger.signal_detected(
        satellite="NOAA-TEST",
        payload={
            "frequency_hz": 137620000,
        },
    )

    service.logger.sdr_error(
        "SDR device timeout"
    )

    results = service.search("SDR")

    assert len(results) == 1
    assert "SDR" in results[0].message

    results = service.search("NOAA-TEST")

    assert len(results) >= 1

    service.close()


def test_filter_by_satellite(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="replay"
    )

    service.logger.satellite_acquired("SAT-A")
    service.logger.satellite_acquired("SAT-B")
    service.logger.satellite_lost("SAT-A")

    events = service.events(
        satellite="SAT-A"
    )

    assert len(events) == 2
    assert all(
        event.satellite == "SAT-A"
        for event in events
    )

    service.close()


def test_filter_by_severity(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    service.logger.warning(
        "Receiver signal weak"
    )

    service.logger.error(
        "Receiver failure"
    )

    warnings = service.events(
        severity=MissionEventSeverity.WARNING
    )

    errors = service.events(
        severity=MissionEventSeverity.ERROR
    )

    assert len(warnings) == 1
    assert len(errors) == 1

    service.close()


def test_statistics(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    service.logger.satellite_acquired("SAT-A")
    service.logger.packet_received(
        packet_id="P1"
    )
    service.logger.telemetry_received(
        packet_id="P1"
    )
    service.logger.crc_error(
        packet_id="P2"
    )

    statistics = service.statistics()

    assert statistics.total_events == 5
    assert statistics.success_events >= 3
    assert statistics.packet_events == 1
    assert statistics.telemetry_events == 1
    assert statistics.crc_errors == 1
    assert statistics.error_events == 1

    service.close()


def test_session_counters(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    session = service.start_mission(
        mode="replay",
        satellite="SAT-A",
    )

    service.logger.packet_received(
        packet_id="P1"
    )

    service.logger.packet_received(
        packet_id="P2"
    )

    service.logger.telemetry_received(
        packet_id="P1"
    )

    service.logger.error(
        "test error"
    )

    updated = service.database.get_session(
        session.mission_id
    )

    assert updated is not None
    assert updated.packet_count == 2
    assert updated.telemetry_count == 1
    assert updated.error_count == 1
    assert updated.event_count == 5

    service.close()


def test_list_events_ordered_newest_first(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    service.logger.log(
        MissionEventType.CUSTOM,
        "First",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    service.logger.log(
        MissionEventType.CUSTOM,
        "Second",
        timestamp="2026-01-01T00:00:02+00:00",
    )

    service.logger.log(
        MissionEventType.CUSTOM,
        "Third",
        timestamp="2026-01-01T00:00:01+00:00",
    )

    events = service.events(
        event_type=MissionEventType.CUSTOM
    )

    assert len(events) == 3
    assert events[0].message == "Second"
    assert events[1].message == "Third"
    assert events[2].message == "First"

    service.close()


def test_event_serialization():
    database = MissionLogDatabase(":memory:")
    logger = MissionLogger(
        database,
        mission_id="mission-test",
    )

    event = logger.log(
        MissionEventType.CUSTOM,
        "Test event",
        severity=MissionEventSeverity.WARNING,
        satellite="SAT-A",
        payload={
            "value": 123,
        },
    )

    data = event.to_dict()

    assert data["event_id"] == event.event_id
    assert data["event_type"] == "custom"
    assert data["severity"] == "warning"
    assert data["satellite"] == "SAT-A"
    assert data["payload"]["value"] == 123

    database.close()


def test_empty_search_returns_recent_events(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    service.logger.warning("Warning A")
    service.logger.warning("Warning B")

    events = service.search("")

    assert len(events) == 3

    service.close()


def test_pagination(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    for index in range(10):
        service.logger.log(
            MissionEventType.CUSTOM,
            f"Event {index}",
        )

    first = service.events(
        limit=3,
        offset=0,
    )

    second = service.events(
        limit=3,
        offset=3,
    )

    assert len(first) == 3
    assert len(second) == 3
    assert first[0].event_id != second[0].event_id

    service.close()


def test_invalid_pagination(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    try:
        service.events(limit=0)
        assert False
    except ValueError:
        pass

    try:
        service.events(offset=-1)
        assert False
    except ValueError:
        pass

    service.close()


def test_clearing_log(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    service.start_mission(
        mode="live"
    )

    service.logger.warning("Something happened")

    assert service.statistics().total_events == 2

    service.clear()

    assert service.statistics().total_events == 0
    assert service.session is None

    service.close()


def test_service_status(tmp_path):
    service = MissionLogService(
        tmp_path / "mission.db"
    )

    status = service.status()

    assert status["active"] is False
    assert status["session"] is None
    assert status["statistics"]["total_events"] == 0

    service.start_mission(
        mode="replay",
        satellite="TEST-SAT",
    )

    status = service.status()

    assert status["active"] is True
    assert status["session"]["satellite"] == "TEST-SAT"

    service.close()
