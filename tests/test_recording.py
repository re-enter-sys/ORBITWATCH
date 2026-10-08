from __future__ import annotations

import json

import pytest

from groundstation.recording import (
    EventRecordingReader,
    IQChunk,
    IQRecordingReader,
    RecordingEvent,
    RecordingIntegrityError,
    RecordingService,
    ReplayController,
    ReplayState,
)


def test_iq_recording_round_trip(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_iq_recording(
        sample_rate_hz=2_048_000,
        center_frequency_hz=145_800_000,
        satellite="TEST-SAT",
    )

    samples = (
        complex(1.0, 0.0),
        complex(0.5, -0.5),
        complex(-1.0, 0.25),
        complex(0.0, 1.0),
    )

    assert writer.write(samples) == 4

    metadata = writer.close()

    assert metadata.sample_count == 4
    assert metadata.recording_id.startswith("iq-")
    assert metadata.satellite == "TEST-SAT"

    reader = IQRecordingReader(
        tmp_path / "recordings" / "iq" / f"{metadata.recording_id}.iq"
    )

    assert reader.validate() is True

    restored = []

    for chunk in reader.iter_samples(chunk_size=2):
        restored.extend(chunk)

    assert len(restored) == 4
    assert restored[0].real == pytest.approx(1.0)
    assert restored[1].imag == pytest.approx(-0.5)


def test_iq_chunk_recording(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_iq_recording(
        sample_rate_hz=1000,
        center_frequency_hz=145800000,
    )

    chunk = IQChunk(
        samples=(1 + 2j, 3 + 4j),
        sample_rate_hz=1000,
        center_frequency_hz=145800000,
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert writer.write_chunk(chunk) == 2

    metadata = writer.close()

    assert metadata.sample_count == 2
    assert metadata.duration_seconds == pytest.approx(0.002)


def test_event_recording_round_trip(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_event_recording(
        satellite="TEST-SAT",
        description="Telemetry replay",
    )

    writer.write_mapping(
        "telemetry",
        {
            "temperature_c": 21.5,
            "voltage_v": 3.7,
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    writer.write(
        RecordingEvent(
            timestamp="2026-01-01T00:00:01+00:00",
            event_type="packet",
            payload={
                "protocol": "AX.25",
                "valid": True,
            },
        )
    )

    metadata = writer.close()

    assert metadata.event_count == 2

    reader = EventRecordingReader(
        tmp_path
        / "recordings"
        / "events"
        / f"{metadata.recording_id}.jsonl"
    )

    assert reader.validate() is True

    events = list(reader.iter_events())

    assert len(events) == 2
    assert events[0].event_type == "telemetry"
    assert events[0].payload["temperature_c"] == 21.5
    assert events[1].event_type == "packet"


def test_recording_listing(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    iq_writer = service.start_iq_recording(
        sample_rate_hz=1000,
        center_frequency_hz=145800000,
    )
    iq_writer.write((1 + 0j,))
    iq_metadata = iq_writer.close()

    event_writer = service.start_event_recording()
    event_writer.write_mapping("packet", {"id": "001"})
    event_metadata = event_writer.close()

    recordings = service.list_recordings()

    ids = {item.recording_id for item in recordings}

    assert iq_metadata.recording_id in ids
    assert event_metadata.recording_id in ids
    assert len(recordings) == 2


def test_iq_replay():
    chunks = [
        IQChunk(
            samples=(1 + 0j, 2 + 0j),
            sample_rate_hz=1000,
            center_frequency_hz=145800000,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
        IQChunk(
            samples=(3 + 0j, 4 + 0j),
            sample_rate_hz=1000,
            center_frequency_hz=145800000,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
    ]

    received = []

    controller = ReplayController(speed=100.0, realtime=False)

    status = controller.replay_iq(
        chunks,
        received.append,
        total_samples=4,
    )

    assert status.state == ReplayState.COMPLETED
    assert status.progress == pytest.approx(1.0)
    assert status.statistics.chunks_processed == 2
    assert status.statistics.samples_processed == 4
    assert len(received) == 2


def test_event_replay():
    events = [
        RecordingEvent(
            timestamp="2026-01-01T00:00:00+00:00",
            event_type="packet",
            payload={"id": "001"},
        ),
        RecordingEvent(
            timestamp="2026-01-01T00:00:01+00:00",
            event_type="telemetry",
            payload={"temperature": 20},
        ),
    ]

    received = []

    controller = ReplayController(
        speed=100.0,
        realtime=False,
    )

    status = controller.replay_events(
        events,
        received.append,
    )

    assert status.state == ReplayState.COMPLETED
    assert status.statistics.events_processed == 2
    assert [event.event_type for event in received] == [
        "packet",
        "telemetry",
    ]


def test_replay_speed_validation():
    with pytest.raises(ValueError):
        ReplayController(speed=0)

    controller = ReplayController()

    with pytest.raises(ValueError):
        controller.set_speed(0)


def test_replay_pause_resume_stop():
    controller = ReplayController()

    controller._state = ReplayState.PLAYING
    controller.pause()

    assert controller.state == ReplayState.PAUSED

    controller.resume()

    assert controller.state == ReplayState.PLAYING

    controller.stop()

    assert controller.state == ReplayState.STOPPED


def test_recording_checksum_detects_corruption(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_iq_recording(
        sample_rate_hz=1000,
        center_frequency_hz=145800000,
    )

    writer.write((1 + 0j, 2 + 0j))
    metadata = writer.close()

    data_path = (
        tmp_path
        / "recordings"
        / "iq"
        / f"{metadata.recording_id}.iq"
    )

    with data_path.open("ab") as file:
        file.write(b"corruption")

    reader = IQRecordingReader(data_path)

    with pytest.raises(RecordingIntegrityError):
        reader.validate()


def test_event_checksum_detects_corruption(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_event_recording()
    writer.write_mapping("packet", {"id": "001"})
    metadata = writer.close()

    data_path = (
        tmp_path
        / "recordings"
        / "events"
        / f"{metadata.recording_id}.jsonl"
    )

    with data_path.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:01+00:00",
                    "event_type": "corrupted",
                    "payload": {},
                }
            )
            + "\n"
        )

    reader = EventRecordingReader(data_path)

    with pytest.raises(RecordingIntegrityError):
        reader.validate()


def test_service_validation(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_event_recording()
    writer.write_mapping("packet", {"id": "TEST"})
    metadata = writer.close()

    assert service.validate(metadata.recording_id) is True


def test_event_metadata_is_valid_json(tmp_path):
    service = RecordingService(tmp_path / "recordings")

    writer = service.start_event_recording(
        satellite="TEST-SAT",
    )
    metadata = writer.close()

    metadata_path = (
        tmp_path
        / "recordings"
        / "events"
        / f"{metadata.recording_id}.json"
    )

    parsed = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    assert parsed["recording_id"] == metadata.recording_id
    assert parsed["recording_type"] == "events"
