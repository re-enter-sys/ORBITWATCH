from datetime import datetime, timezone

import pytest

from groundstation.protocols.ax25 import (
    AX25Address,
    AX25Parser,
    encode_ax25_ui_frame,
)
from groundstation.protocols.kiss import (
    KISSFrameType,
    KISSParser,
    encode_kiss_frame,
)
from groundstation.telemetry import (
    TelemetryDatabase,
    TelemetryDecoder,
    TelemetryDecoderRegistry,
    TelemetryEngine,
    TelemetryRecord,
)


def timestamp():
    return datetime(
        2026,
        10,
        8,
        12,
        0,
        tzinfo=timezone.utc,
    )


def make_engine(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    return TelemetryEngine(
        database=database,
        persist=True,
    )


def test_engine_processes_mapping(tmp_path):
    engine = make_engine(tmp_path)

    result = engine.process_mapping(
        {
            "TEMP": 24.5,
            "BATT": 7.4,
        },
        satellite="ORBIT-1",
        timestamp=timestamp(),
    )

    assert result.satellite == "ORBIT-1"
    assert result.get("temp") == 24.5
    assert result.get("batt") == 7.4
    assert result.field_count == 2
    assert result.database_id is not None
    assert engine.processed_count == 1
    assert engine.successful_count == 1

    engine.close()


def test_engine_processes_json(tmp_path):
    engine = make_engine(tmp_path)

    result = engine.process_json(
        '{"TEMP": 22.1, "BATT": 7.8}',
        satellite="ORBIT-2",
        timestamp=timestamp(),
    )

    assert result.get("temp") == 22.1
    assert result.get("batt") == 7.8
    assert result.database_id is not None

    engine.close()


def test_engine_processes_key_value(tmp_path):
    engine = make_engine(tmp_path)

    result = engine.process_key_value(
        "TEMP=24.5,BATT=7.4,MODE=SAFE",
        satellite="ORBIT-3",
        timestamp=timestamp(),
    )

    assert result.get("temp") == 24.5
    assert result.get("batt") == 7.4
    assert result.get("mode") == "SAFE"

    engine.close()


def test_engine_can_disable_persistence(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    engine = TelemetryEngine(
        database=database,
        persist=False,
    )

    result = engine.process_mapping(
        {"TEMP": 20},
        satellite="ORBIT-4",
        timestamp=timestamp(),
    )

    assert result.database_id is None
    assert database.count() == 0

    engine.close()


def test_engine_process_existing_record(tmp_path):
    engine = make_engine(tmp_path)

    record = TelemetryRecord(
        satellite="ORBIT-5",
        timestamp=timestamp(),
    )

    record.add(
        "temperature",
        25.0,
        unit="C",
    )

    result = engine.process_record(record)

    assert result.record is record
    assert result.decoded.get("temperature") == 25.0
    assert result.database_id is not None
    assert engine.database.count() == 1

    engine.close()


def test_engine_applies_registered_decoder(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    registry = TelemetryDecoderRegistry()

    registry.register(
        "ORBIT-6",
        TelemetryDecoder(
            name="orbit6",
            decoder=lambda record: {
                "temperature_c": {
                    "value": record.get("temp"),
                    "unit": "C",
                },
            },
        ),
    )

    engine = TelemetryEngine(
        registry=registry,
        database=database,
    )

    result = engine.process_key_value(
        "TEMP=26.5,BATT=7.5",
        satellite="ORBIT-6",
        timestamp=timestamp(),
    )

    assert result.decoded.decoder == "orbit6"
    assert result.get("temperature_c") == 26.5
    assert result.decoded.values["temperature_c"].unit == "C"

    engine.close()


def test_engine_processes_ax25(tmp_path):
    engine = make_engine(tmp_path)

    frame_bytes = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("ORBIT1"),
        information=b"TEMP=23.5,BATT=7.4",
    )

    frame = AX25Parser().parse(frame_bytes)

    result = engine.process_ax25(
        frame,
        timestamp=timestamp(),
    )

    assert result.satellite == "ORBIT1"
    assert result.get("temp") == 23.5
    assert result.get("batt") == 7.4
    assert result.database_id is not None

    engine.close()


def test_engine_processes_kiss(tmp_path):
    engine = make_engine(tmp_path)

    ax25_bytes = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("ORBIT2"),
        information=b"TEMP=21.2,BATT=7.3",
    )

    kiss_bytes = encode_kiss_frame(
        ax25_bytes,
        command=KISSFrameType.DATA,
    )

    kiss_frames = KISSParser().feed(kiss_bytes)

    assert len(kiss_frames) == 1

    result = engine.process_kiss(
        kiss_frames[0],
        timestamp=timestamp(),
    )

    assert result.satellite == "ORBIT2"
    assert result.get("temp") == 21.2
    assert result.get("batt") == 7.3
    assert result.database_id is not None

    engine.close()


def test_engine_rejects_invalid_record(tmp_path):
    engine = make_engine(tmp_path)

    with pytest.raises(TypeError):
        engine.process_record("invalid")

    engine.close()


def test_engine_rejects_non_ui_ax25(tmp_path):
    engine = make_engine(tmp_path)

    frame_bytes = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("ORBIT3"),
        information=b"TEMP=20",
    )

    parsed = AX25Parser().parse(frame_bytes)

    object.__setattr__(
        parsed,
        "control",
        0x13,
    )

    with pytest.raises(ValueError):
        engine.process_ax25(parsed)

    engine.close()


def test_engine_rejects_non_data_kiss(tmp_path):
    engine = make_engine(tmp_path)

    ax25_bytes = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("ORBIT4"),
        information=b"TEMP=20",
    )

    kiss_bytes = encode_kiss_frame(
        ax25_bytes,
        command=KISSFrameType.TX_DELAY,
    )

    frame = KISSParser().feed(kiss_bytes)[0]

    with pytest.raises(ValueError):
        engine.process_kiss(frame)

    engine.close()


def test_engine_processes_multiple_records(tmp_path):
    engine = make_engine(tmp_path)

    records = []

    for index in range(3):
        record = TelemetryRecord(
            satellite="ORBIT-7",
            timestamp=timestamp(),
        )

        record.add(
            "temperature",
            float(index),
        )

        records.append(record)

    results = engine.process_records(records)

    assert len(results) == 3
    assert engine.processed_count == 3
    assert engine.successful_count == 3
    assert engine.database.count() == 3

    engine.close()


def test_engine_statistics_reset(tmp_path):
    engine = make_engine(tmp_path)

    engine.process_mapping(
        {"TEMP": 20},
        satellite="ORBIT-8",
        timestamp=timestamp(),
    )

    assert engine.processed_count == 1

    engine.reset_statistics()

    assert engine.processed_count == 0
    assert engine.successful_count == 0
    assert engine.failed_count == 0

    engine.close()


def test_result_serialization(tmp_path):
    engine = make_engine(tmp_path)

    result = engine.process_mapping(
        {"TEMP": 28.5},
        satellite="ORBIT-9",
        timestamp=timestamp(),
    )

    data = result.to_dict()

    assert data["satellite"] == "ORBIT-9"
    assert data["database_id"] is not None
    assert data["values"]["temp"]["value"] == 28.5

    engine.close()


def test_engine_context_manager(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    with TelemetryEngine(
        database=database,
    ) as engine:
        result = engine.process_mapping(
            {"TEMP": 19.5},
            satellite="ORBIT-10",
            timestamp=timestamp(),
        )

        assert result.database_id is not None
