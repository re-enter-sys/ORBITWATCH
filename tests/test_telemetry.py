from __future__ import annotations

from datetime import datetime, timezone

import pytest

from groundstation.protocols.telemetry import (
    TelemetryField,
    TelemetryPacket,
    TelemetryParser,
    fields_from_mapping,
)


SATELLITE = "TESTSAT"
TIMESTAMP = datetime(
    2026,
    10,
    7,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)


# ---------------------------------------------------------------------------
# TelemetryField
# ---------------------------------------------------------------------------


def test_telemetry_field_creation() -> None:
    field = TelemetryField(
        name="temperature",
        value=24.5,
        raw_value="24.5",
        unit="C",
    )

    assert field.name == "temperature"
    assert field.value == 24.5
    assert field.raw_value == "24.5"
    assert field.unit == "C"


def test_telemetry_field_without_unit() -> None:
    field = TelemetryField(
        name="mode",
        value="SAFE",
        raw_value="SAFE",
    )

    assert field.name == "mode"
    assert field.value == "SAFE"
    assert field.raw_value == "SAFE"
    assert field.unit is None


def test_telemetry_field_empty_name_rejected() -> None:
    with pytest.raises(ValueError):
        TelemetryField(
            name="",
            value=10,
            raw_value="10",
        )


def test_telemetry_field_whitespace_name_rejected() -> None:
    with pytest.raises(ValueError):
        TelemetryField(
            name="   ",
            value=10,
            raw_value="10",
        )


def test_telemetry_field_preserves_raw_value() -> None:
    field = TelemetryField(
        name="temperature",
        value=24.5,
        raw_value="24.5C",
        unit="C",
    )

    assert field.value == 24.5
    assert field.raw_value == "24.5C"
    assert field.unit == "C"


# ---------------------------------------------------------------------------
# TelemetryPacket
# ---------------------------------------------------------------------------


def test_telemetry_packet_creation() -> None:
    fields = (
        TelemetryField(
            name="temperature",
            value=25.0,
            raw_value="25.0",
            unit="C",
        ),
        TelemetryField(
            name="voltage",
            value=7.4,
            raw_value="7.4",
            unit="V",
        ),
    )

    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=fields,
        timestamp=TIMESTAMP,
        source="ground-test",
        sequence=42,
    )

    assert packet.satellite == SATELLITE
    assert packet.fields == fields
    assert packet.timestamp == TIMESTAMP
    assert packet.source == "ground-test"
    assert packet.sequence == 42


def test_telemetry_packet_default_source() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(),
        timestamp=TIMESTAMP,
    )

    assert packet.source == "unknown"
    assert packet.sequence is None


def test_telemetry_packet_field_count() -> None:
    fields = (
        TelemetryField(
            name="temperature",
            value=25.0,
            raw_value="25.0",
        ),
        TelemetryField(
            name="voltage",
            value=7.4,
            raw_value="7.4",
        ),
    )

    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=fields,
        timestamp=TIMESTAMP,
    )

    assert packet.field_count == 2


def test_telemetry_packet_empty_fields() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(),
        timestamp=TIMESTAMP,
    )

    assert packet.field_count == 0
    assert packet.fields == ()


def test_telemetry_packet_rejects_empty_satellite() -> None:
    with pytest.raises(ValueError):
        TelemetryPacket(
            satellite="",
            fields=(),
            timestamp=TIMESTAMP,
        )


def test_telemetry_packet_rejects_whitespace_satellite() -> None:
    with pytest.raises(ValueError):
        TelemetryPacket(
            satellite="   ",
            fields=(),
            timestamp=TIMESTAMP,
        )


def test_telemetry_packet_requires_timezone_aware_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        10,
        7,
        12,
        0,
        0,
    )

    with pytest.raises(ValueError):
        TelemetryPacket(
            satellite=SATELLITE,
            fields=(),
            timestamp=naive_timestamp,
        )


def test_telemetry_packet_get() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(
            TelemetryField(
                name="temperature",
                value=25.5,
                raw_value="25.5",
            ),
            TelemetryField(
                name="voltage",
                value=7.4,
                raw_value="7.4",
            ),
        ),
        timestamp=TIMESTAMP,
    )

    assert packet.get("temperature") == 25.5
    assert packet.get("voltage") == 7.4


def test_telemetry_packet_get_is_case_insensitive() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(
            TelemetryField(
                name="Temperature",
                value=25.5,
                raw_value="25.5",
            ),
        ),
        timestamp=TIMESTAMP,
    )

    assert packet.get("temperature") == 25.5
    assert packet.get("TEMPERATURE") == 25.5
    assert packet.get(" Temperature ") == 25.5


def test_telemetry_packet_get_missing_returns_none() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(),
        timestamp=TIMESTAMP,
    )

    assert packet.get("missing") is None


def test_telemetry_packet_get_missing_custom_default() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(),
        timestamp=TIMESTAMP,
    )

    assert packet.get("missing", "UNKNOWN") == "UNKNOWN"


def test_telemetry_packet_as_dict() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(
            TelemetryField(
                name="temperature",
                value=25.0,
                raw_value="25.0",
            ),
            TelemetryField(
                name="mode",
                value="SAFE",
                raw_value="SAFE",
            ),
        ),
        timestamp=TIMESTAMP,
    )

    assert packet.as_dict() == {
        "temperature": 25.0,
        "mode": "SAFE",
    }


def test_telemetry_packet_to_dict() -> None:
    packet = TelemetryPacket(
        satellite=SATELLITE,
        fields=(
            TelemetryField(
                name="temperature",
                value=25.0,
                raw_value="25.0",
            ),
        ),
        timestamp=TIMESTAMP,
        source="SDR",
        sequence=7,
    )

    result = packet.to_dict()

    assert result == {
        "satellite": SATELLITE,
        "timestamp": TIMESTAMP.isoformat(),
        "source": "SDR",
        "sequence": 7,
        "fields": {
            "temperature": 25.0,
        },
    }


# ---------------------------------------------------------------------------
# TelemetryParser
# ---------------------------------------------------------------------------


def test_parser_simple_equals_payload() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=24.5,BATT=7.4,MODE=SAFE",
        SATELLITE,
        source="replay",
        timestamp=TIMESTAMP,
        sequence=1,
    )

    assert packet.satellite == SATELLITE
    assert packet.source == "replay"
    assert packet.timestamp == TIMESTAMP
    assert packet.sequence == 1

    assert packet.get("TEMP") == 24.5
    assert packet.get("BATT") == 7.4
    assert packet.get("MODE") == "SAFE"


def test_parser_colon_payload() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP:24.5 BATT:7.4 MODE:SAFE",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TEMP") == 24.5
    assert packet.get("BATT") == 7.4
    assert packet.get("MODE") == "SAFE"


def test_parser_bytes_payload() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        b"TEMP=24.5,BATT=7.4",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TEMP") == 24.5
    assert packet.get("BATT") == 7.4


def test_parser_mixed_delimiters() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=24.5;BATT=7.4 MODE=SAFE",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TEMP") == 24.5
    assert packet.get("BATT") == 7.4
    assert packet.get("MODE") == "SAFE"


def test_parser_integer_value() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "COUNT=42",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("COUNT") == 42
    assert isinstance(packet.get("COUNT"), int)


def test_parser_negative_integer() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=-12",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TEMP") == -12


def test_parser_float_value() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=-5.25",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TEMP") == -5.25
    assert isinstance(packet.get("TEMP"), float)


def test_parser_positive_value() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=+12.5",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TEMP") == 12.5


def test_parser_value_with_celsius_unit() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=24.5C",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    field = packet.fields[0]

    assert field.name == "TEMP"
    assert field.value == 24.5
    assert field.raw_value == "24.5C"
    assert field.unit == "C"


def test_parser_value_with_voltage_unit() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "BATT=7.4V",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    field = packet.fields[0]

    assert field.value == 7.4
    assert field.raw_value == "7.4V"
    assert field.unit == "V"


def test_parser_percentage_unit() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "BATTERY=87%",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    field = packet.fields[0]

    assert field.value == 87
    assert field.raw_value == "87%"
    assert field.unit == "%"


def test_parser_boolean_true() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "GPS=true",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("GPS") is True


def test_parser_boolean_false() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "GPS=false",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("GPS") is False


def test_parser_boolean_is_case_insensitive() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "A=TRUE,B=False",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("A") is True
    assert packet.get("B") is False


def test_parser_on_off_values() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TX=ON,RX=off",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("TX") is True
    assert packet.get("RX") is False


def test_parser_string_value() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "MODE=SAFE",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.get("MODE") == "SAFE"
    assert isinstance(packet.get("MODE"), str)


def test_parser_field_count() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=24.5,BATT=7.4,MODE=SAFE",
        SATELLITE,
        timestamp=TIMESTAMP,
    )

    assert packet.field_count == 3


def test_parser_default_timestamp_is_timezone_aware() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=24.5",
        SATELLITE,
    )

    assert packet.timestamp.tzinfo is not None
    assert packet.timestamp.utcoffset() is not None


def test_parser_rejects_naive_timestamp() -> None:
    parser = TelemetryParser()

    naive_timestamp = datetime(
        2026,
        10,
        7,
        12,
        0,
        0,
    )

    with pytest.raises(ValueError):
        parser.parse(
            "TEMP=24.5",
            SATELLITE,
            timestamp=naive_timestamp,
        )


def test_parser_rejects_empty_payload() -> None:
    parser = TelemetryParser()

    with pytest.raises(ValueError):
        parser.parse(
            "",
            SATELLITE,
            timestamp=TIMESTAMP,
        )


def test_parser_rejects_payload_without_fields() -> None:
    parser = TelemetryParser()

    with pytest.raises(ValueError):
        parser.parse(
            "THIS IS NOT TELEMETRY",
            SATELLITE,
            timestamp=TIMESTAMP,
        )


def test_parser_rejects_invalid_payload_type() -> None:
    parser = TelemetryParser()

    with pytest.raises(TypeError):
        parser.parse(
            12345,  # type: ignore[arg-type]
            SATELLITE,
            timestamp=TIMESTAMP,
        )


def test_parser_requires_satellite() -> None:
    parser = TelemetryParser()

    with pytest.raises(ValueError):
        parser.parse(
            "TEMP=24.5",
            "",
            timestamp=TIMESTAMP,
        )


# ---------------------------------------------------------------------------
# Internal value conversion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_value", "expected", "expected_unit"),
    [
        ("24.5", 24.5, None),
        ("7", 7, None),
        ("-12", -12, None),
        ("+12", 12, None),
        ("24.5C", 24.5, "C"),
        ("7.4V", 7.4, "V"),
        ("87%", 87, "%"),
        ("true", True, None),
        ("false", False, None),
        ("on", True, None),
        ("off", False, None),
        ("SAFE", "SAFE", None),
    ],
)
def test_convert_value(
    raw_value: str,
    expected: object,
    expected_unit: str | None,
) -> None:
    value, unit = TelemetryParser._convert_value(raw_value)

    assert value == expected
    assert unit == expected_unit


# ---------------------------------------------------------------------------
# Mapping conversion
# ---------------------------------------------------------------------------


def test_fields_from_mapping() -> None:
    fields = fields_from_mapping(
        {
            "temperature": 25.0,
            "voltage": 7.4,
            "mode": "SAFE",
        }
    )

    assert len(fields) == 3

    assert fields[0].name == "temperature"
    assert fields[0].value == 25.0
    assert fields[0].raw_value == "25.0"

    assert fields[1].name == "voltage"
    assert fields[1].value == 7.4
    assert fields[1].raw_value == "7.4"

    assert fields[2].name == "mode"
    assert fields[2].value == "SAFE"
    assert fields[2].raw_value == "SAFE"


def test_fields_from_mapping_empty() -> None:
    assert fields_from_mapping({}) == ()


def test_fields_from_mapping_converts_names_to_strings() -> None:
    fields = fields_from_mapping(
        {
            123: "VALUE",
        }
    )

    assert fields[0].name == "123"
    assert fields[0].value == "VALUE"
    assert fields[0].raw_value == "VALUE"


# ---------------------------------------------------------------------------
# End-to-end telemetry protocol behavior
# ---------------------------------------------------------------------------


def test_telemetry_end_to_end() -> None:
    parser = TelemetryParser()

    packet = parser.parse(
        "TEMP=24.5C,BATT=7.4V,CURRENT=1.2A,GPS=true,MODE=SAFE",
        "ORBITWATCH-TEST",
        source="SDR replay",
        timestamp=TIMESTAMP,
        sequence=100,
    )

    assert packet.satellite == "ORBITWATCH-TEST"
    assert packet.source == "SDR replay"
    assert packet.sequence == 100

    assert packet.get("TEMP") == 24.5
    assert packet.get("BATT") == 7.4
    assert packet.get("CURRENT") == 1.2
    assert packet.get("GPS") is True
    assert packet.get("MODE") == "SAFE"

    assert packet.field_count == 5

    result = packet.to_dict()

    assert result["satellite"] == "ORBITWATCH-TEST"
    assert result["source"] == "SDR replay"
    assert result["sequence"] == 100
    assert result["fields"]["TEMP"] == 24.5
    assert result["fields"]["BATT"] == 7.4
    assert result["fields"]["GPS"] is True
