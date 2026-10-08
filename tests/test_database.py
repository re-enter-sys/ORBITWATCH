from datetime import datetime, timezone

import pytest

from src.groundstation.telemetry.database import (
    TelemetryDatabase,
)
from src.groundstation.telemetry.parser import (
    TelemetryRecord,
    parse_key_value,
)


def make_record(
    satellite="TESTSAT",
    packet_id="PKT-001",
    timestamp=None,
):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return parse_key_value(
        "TEMP=24.5 C,BATT=7.4 V,MODE=SAFE",
        satellite=satellite,
        timestamp=timestamp,
        source="test",
        packet_id=packet_id,
        valid=True,
        crc_ok=True,
        metadata={
            "test": True,
        },
    )


def test_database_creates_schema(tmp_path):
    path = tmp_path / "telemetry.db"

    database = TelemetryDatabase(path)

    assert path.exists()
    assert database.count() == 0

    database.close()


def test_database_insert_record(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    record = make_record()

    record_id = database.insert(record)

    assert record_id > 0
    assert database.count() == 1


def test_database_count_by_satellite(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(
            satellite="SAT-A",
            packet_id="A-001",
        )
    )

    database.insert(
        make_record(
            satellite="SAT-B",
            packet_id="B-001",
        )
    )

    database.insert(
        make_record(
            satellite="SAT-A",
            packet_id="A-002",
        )
    )

    assert database.count() == 3
    assert database.count("SAT-A") == 2
    assert database.count("SAT-B") == 1


def test_database_latest(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    first = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    second = datetime(
        2026,
        1,
        1,
        13,
        0,
        tzinfo=timezone.utc,
    )

    database.insert(
        make_record(
            packet_id="PKT-001",
            timestamp=first,
        )
    )

    database.insert(
        make_record(
            packet_id="PKT-002",
            timestamp=second,
        )
    )

    latest = database.latest()

    assert latest is not None
    assert latest["packet_id"] == "PKT-002"


def test_database_latest_by_satellite(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(
            satellite="SAT-A",
            packet_id="A-001",
        )
    )

    database.insert(
        make_record(
            satellite="SAT-B",
            packet_id="B-001",
        )
    )

    latest = database.latest("SAT-B")

    assert latest is not None
    assert latest["satellite"] == "SAT-B"
    assert latest["packet_id"] == "B-001"


def test_database_history(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(packet_id="PKT-001")
    )

    database.insert(
        make_record(packet_id="PKT-002")
    )

    history = database.history()

    assert len(history) == 2
    assert history[0]["packet_id"] == "PKT-002"
    assert history[1]["packet_id"] == "PKT-001"


def test_database_history_limit(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    for index in range(5):
        database.insert(
            make_record(
                packet_id=f"PKT-{index}"
            )
        )

    history = database.history(limit=2)

    assert len(history) == 2


def test_database_history_invalid_limit(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    with pytest.raises(ValueError):
        database.history(limit=0)


def test_database_history_by_satellite(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(
            satellite="SAT-A",
            packet_id="A-001",
        )
    )

    database.insert(
        make_record(
            satellite="SAT-B",
            packet_id="B-001",
        )
    )

    history = database.history(
        satellite="SAT-A"
    )

    assert len(history) == 1
    assert history[0]["satellite"] == "SAT-A"


def test_database_preserves_values(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record()
    )

    latest = database.latest()

    assert latest is not None

    assert latest["values"]["temp"]["value"] == 24.5
    assert latest["values"]["temp"]["unit"] == "C"

    assert latest["values"]["batt"]["value"] == 7.4
    assert latest["values"]["batt"]["unit"] == "V"

    assert latest["values"]["mode"]["value"] == "SAFE"


def test_database_preserves_metadata(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record()
    )

    latest = database.latest()

    assert latest is not None
    assert latest["metadata"]["test"] is True


def test_database_preserves_crc_state(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record()
    )

    latest = database.latest()

    assert latest is not None
    assert latest["valid"] is True
    assert latest["crc_ok"] is True


def test_database_packet_lookup(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(
            packet_id="SPECIAL-001"
        )
    )

    result = database.find_by_packet_id(
        "SPECIAL-001"
    )

    assert result is not None
    assert result["packet_id"] == "SPECIAL-001"


def test_database_missing_packet_returns_none(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    assert (
        database.find_by_packet_id(
            "DOES-NOT-EXIST"
        )
        is None
    )


def test_database_satellite_list(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(
            satellite="SAT-Z"
        )
    )

    database.insert(
        make_record(
            satellite="SAT-A"
        )
    )

    database.insert(
        make_record(
            satellite="SAT-Z",
            packet_id="Z-002",
        )
    )

    assert database.list_satellites() == (
        "SAT-A",
        "SAT-Z",
    )


def test_database_insert_many(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    records = [
        make_record(packet_id="PKT-001"),
        make_record(packet_id="PKT-002"),
        make_record(packet_id="PKT-003"),
    ]

    ids = database.insert_many(records)

    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert database.count() == 3


def test_database_delete_all(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    database.insert(
        make_record(packet_id="PKT-001")
    )

    database.insert(
        make_record(packet_id="PKT-002")
    )

    assert database.count() == 2

    deleted = database.delete_all()

    assert deleted == 2
    assert database.count() == 0


def test_database_reopens_existing_file(tmp_path):
    path = tmp_path / "telemetry.db"

    database = TelemetryDatabase(path)

    database.insert(
        make_record()
    )

    database.close()

    reopened = TelemetryDatabase(path)

    assert reopened.count() == 1

    latest = reopened.latest()

    assert latest is not None
    assert latest["satellite"] == "TESTSAT"

    reopened.close()


def test_database_context_manager(tmp_path):
    path = tmp_path / "telemetry.db"

    with TelemetryDatabase(path) as database:
        database.insert(
            make_record()
        )

        assert database.count() == 1


def test_database_rejects_invalid_record(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    with pytest.raises(TypeError):
        database.insert("invalid")


def test_database_bytes_raw_payload(tmp_path):
    database = TelemetryDatabase(
        tmp_path / "telemetry.db"
    )

    record = TelemetryRecord(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        raw_payload=b"TEMP=25",
    )

    record.add(
        "temp",
        25,
        unit="C",
        raw_value="25",
    )

    database.insert(record)

    latest = database.latest()

    assert latest is not None
    assert latest["raw_payload"] == "TEMP=25"
