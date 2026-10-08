"""
Telemetry parsing primitives for OrbitWatch.

This module converts common telemetry representations into
structured, typed telemetry records.

Supported input forms:

- JSON objects
- JSON strings
- key=value text
- key:value text
- comma/semicolon separated telemetry
- mappings supplied directly by Python code
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TelemetryValue:
    """A single normalized telemetry value."""

    name: str
    value: Any
    unit: str | None = None
    data_type: str = "string"
    raw_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the telemetry value."""

        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "data_type": self.data_type,
            "raw_value": self.raw_value,
        }


@dataclass(slots=True)
class TelemetryRecord:
    """Structured telemetry received from a satellite."""

    satellite: str
    timestamp: datetime
    values: dict[str, TelemetryValue] = field(default_factory=dict)
    source: str = "unknown"
    packet_id: str | None = None
    valid: bool = True
    crc_ok: bool | None = None
    raw_payload: str | bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize and validate the telemetry record."""

        if not self.satellite.strip():
            raise ValueError("Satellite name cannot be empty.")

        if self.timestamp.tzinfo is None:
            raise ValueError(
                "Telemetry timestamp must be timezone-aware."
            )

        self.timestamp = self.timestamp.astimezone(timezone.utc)

    def add(
        self,
        name: str,
        value: Any,
        unit: str | None = None,
        data_type: str | None = None,
        raw_value: str | None = None,
    ) -> TelemetryValue:
        """Add or replace a telemetry value."""

        normalized_name = normalize_field_name(name)

        if not normalized_name:
            raise ValueError(
                "Telemetry field name cannot be empty."
            )

        if data_type is None:
            data_type = infer_data_type(value)

        field_value = TelemetryValue(
            name=normalized_name,
            value=value,
            unit=unit,
            data_type=data_type,
            raw_value=raw_value,
        )

        self.values[normalized_name] = field_value

        return field_value

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """Return a telemetry value."""

        field_value = self.values.get(
            normalize_field_name(name)
        )

        if field_value is None:
            return default

        return field_value.value

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete telemetry record."""

        return {
            "satellite": self.satellite,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "packet_id": self.packet_id,
            "valid": self.valid,
            "crc_ok": self.crc_ok,
            "raw_payload": (
                self.raw_payload.decode(
                    "utf-8",
                    errors="replace",
                )
                if isinstance(self.raw_payload, bytes)
                else self.raw_payload
            ),
            "metadata": dict(self.metadata),
            "values": {
                name: value.to_dict()
                for name, value in self.values.items()
            },
        }


def normalize_field_name(name: str) -> str:
    """Normalize a telemetry field name."""

    text = str(name).strip().lower()

    text = re.sub(
        r"[^a-z0-9_]+",
        "_",
        text,
    )

    text = re.sub(
        r"_+",
        "_",
        text,
    )

    return text.strip("_")


def infer_data_type(value: Any) -> str:
    """Infer a stable telemetry data type."""

    if isinstance(value, bool):
        return "bool"

    if isinstance(value, int) and not isinstance(value, bool):
        return "int"

    if isinstance(value, float):
        return "float"

    if value is None:
        return "null"

    return "string"


def _coerce_scalar(value: Any) -> Any:
    """Convert textual values into useful Python scalar types."""

    if not isinstance(value, str):
        return value

    text = value.strip()

    if not text:
        return ""

    lowered = text.lower()

    if lowered in {"true", "yes", "on"}:
        return True

    if lowered in {"false", "no", "off"}:
        return False

    if lowered in {"null", "none", "nil"}:
        return None

    try:
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text)
    except ValueError:
        pass

    try:
        number = float(text)

        if math.isfinite(number):
            return number
    except ValueError:
        pass

    return text


def _split_value_unit(
    value: str,
) -> tuple[str, str | None]:
    """
    Split a textual value from an optional unit.

    Examples:

        "27.4 C" -> ("27.4", "C")
        "14.2 V" -> ("14.2", "V")
        "1024"   -> ("1024", None)
    """

    match = re.fullmatch(
        r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)"
        r"(?:[eE][+-]?\d+)?)"
        r"\s*([A-Za-z%°/_-]+)?\s*",
        value,
    )

    if not match:
        return value.strip(), None

    return (
        match.group(1),
        match.group(2),
    )


def parse_mapping(
    payload: Mapping[str, Any],
    *,
    satellite: str,
    timestamp: datetime | None = None,
    source: str = "mapping",
    packet_id: str | None = None,
    valid: bool = True,
    crc_ok: bool | None = None,
    raw_payload: str | bytes | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> TelemetryRecord:
    """Parse a Python mapping into a telemetry record."""

    record = TelemetryRecord(
        satellite=satellite,
        timestamp=(
            timestamp
            if timestamp is not None
            else datetime.now(timezone.utc)
        ),
        source=source,
        packet_id=packet_id,
        valid=valid,
        crc_ok=crc_ok,
        raw_payload=raw_payload,
        metadata=dict(metadata or {}),
    )

    for name, value in payload.items():
        unit = None

        if isinstance(value, Mapping):
            unit = value.get("unit")
            value = value.get(
                "value",
                value.get("data"),
            )

        record.add(
            str(name),
            value,
            unit=unit,
        )

    return record


def parse_json(
    payload: str | bytes,
    *,
    satellite: str,
    timestamp: datetime | None = None,
    source: str = "json",
    packet_id: str | None = None,
    valid: bool = True,
    crc_ok: bool | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> TelemetryRecord:
    """Parse a JSON telemetry payload."""

    if isinstance(payload, bytes):
        text = payload.decode(
            "utf-8",
            errors="strict",
        )
    else:
        text = payload

    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid telemetry JSON: {exc}"
        ) from exc

    if not isinstance(decoded, Mapping):
        raise ValueError(
            "Telemetry JSON must contain an object."
        )

    return parse_mapping(
        decoded,
        satellite=satellite,
        timestamp=timestamp,
        source=source,
        packet_id=packet_id,
        valid=valid,
        crc_ok=crc_ok,
        raw_payload=text,
        metadata=metadata,
    )


def parse_key_value(
    payload: str | bytes,
    *,
    satellite: str,
    timestamp: datetime | None = None,
    source: str = "key_value",
    packet_id: str | None = None,
    valid: bool = True,
    crc_ok: bool | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> TelemetryRecord:
    """
    Parse key/value telemetry.

    Accepted separators include:

        TEMP=24.5 C, VOLT=7.4 V
        TEMP:24.5 C; VOLT:7.4 V
        TEMP=24.5,VOLT=7.4
    """

    if isinstance(payload, bytes):
        text = payload.decode(
            "utf-8",
            errors="replace",
        )
    else:
        text = payload

    record = TelemetryRecord(
        satellite=satellite,
        timestamp=(
            timestamp
            if timestamp is not None
            else datetime.now(timezone.utc)
        ),
        source=source,
        packet_id=packet_id,
        valid=valid,
        crc_ok=crc_ok,
        raw_payload=text,
        metadata=dict(metadata or {}),
    )

    chunks = re.split(
        r"[;,]\s*|\s+(?=[A-Za-z_][A-Za-z0-9_-]*\s*[:=])",
        text.strip(),
    )

    for chunk in chunks:
        chunk = chunk.strip()

        if not chunk:
            continue

        match = re.match(
            r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)"
            r"\s*[:=]\s*(.*?)\s*$",
            chunk,
        )

        if not match:
            continue

        name = match.group(1)
        raw_value = match.group(2).strip()

        scalar_text, unit = _split_value_unit(
            raw_value
        )

        value = _coerce_scalar(scalar_text)

        record.add(
            name,
            value,
            unit=unit,
            raw_value=raw_value,
        )

    if not record.values:
        raise ValueError(
            "No telemetry key/value fields were found."
        )

    return record


def parse_telemetry(
    payload: str | bytes | Mapping[str, Any],
    *,
    satellite: str,
    timestamp: datetime | None = None,
    source: str = "auto",
    packet_id: str | None = None,
    valid: bool = True,
    crc_ok: bool | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> TelemetryRecord:
    """Automatically select the appropriate telemetry parser."""

    if isinstance(payload, Mapping):
        return parse_mapping(
            payload,
            satellite=satellite,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            metadata=metadata,
        )

    if isinstance(payload, bytes):
        text = payload.decode(
            "utf-8",
            errors="replace",
        )
    else:
        text = payload

    stripped = text.strip()

    if not stripped:
        raise ValueError(
            "Telemetry payload cannot be empty."
        )

    if stripped.startswith("{"):
        return parse_json(
            text,
            satellite=satellite,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            metadata=metadata,
        )

    return parse_key_value(
        text,
        satellite=satellite,
        timestamp=timestamp,
        source=source,
        packet_id=packet_id,
        valid=valid,
        crc_ok=crc_ok,
        metadata=metadata,
    )
