"""
Generic satellite telemetry representation and parsing.

Telemetry formats differ significantly between satellites.
OrbitWatch therefore separates the generic telemetry model from
mission-specific decoders.

The initial parser supports simple key/value payloads such as:

    TEMP=24.5,BATT=7.4,MODE=SAFE

and:

    TEMP:24.5 BATT:7.4 MODE:SAFE

This provides a deterministic development/replay format while
leaving room for binary spacecraft-specific telemetry decoders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class TelemetryField:
    """One decoded telemetry field."""

    name: str
    value: Any
    raw_value: str
    unit: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Telemetry field name cannot be empty.")


@dataclass(frozen=True)
class TelemetryPacket:
    """Decoded telemetry packet."""

    satellite: str
    fields: tuple[TelemetryField, ...]
    timestamp: datetime
    source: str = "unknown"
    sequence: int | None = None

    def __post_init__(self) -> None:
        if not self.satellite.strip():
            raise ValueError("Telemetry satellite cannot be empty.")

        if self.timestamp.tzinfo is None:
            raise ValueError(
                "Telemetry timestamp must be timezone-aware."
            )

    @property
    def field_count(self) -> int:
        """Return the number of telemetry fields."""
        return len(self.fields)

    def get(self, name: str, default: Any = None) -> Any:
        """Return a telemetry value by field name."""
        normalized = name.strip().lower()

        for field in self.fields:
            if field.name.lower() == normalized:
                return field.value

        return default

    def as_dict(self) -> dict[str, Any]:
        """Return telemetry fields as a dictionary."""
        return {
            field.name: field.value
            for field in self.fields
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable telemetry representation."""
        return {
            "satellite": self.satellite,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "sequence": self.sequence,
            "fields": {
                field.name: field.value
                for field in self.fields
            },
        }


class TelemetryParser:
    """
    Parse generic key/value telemetry payloads.

    Mission-specific parsers can build on the same TelemetryPacket
    model without changing the dashboard/API layer.
    """

    _TOKEN_PATTERN = re.compile(
        r"""
        (?P<name>[A-Za-z][A-Za-z0-9_.-]*)
        \s*(?:=|:)
        \s*
        (?P<value>
            [^,\s;]+
        )
        """,
        re.VERBOSE,
    )

    def parse(
        self,
        payload: str | bytes,
        satellite: str,
        *,
        source: str = "unknown",
        timestamp: datetime | None = None,
        sequence: int | None = None,
    ) -> TelemetryPacket:
        """
        Parse a textual telemetry payload.

        Args:
            payload: Telemetry payload.
            satellite: Satellite identifier/callsign.
            source: Source description.
            timestamp: Optional packet timestamp.
            sequence: Optional packet sequence number.

        Returns:
            TelemetryPacket.
        """
        if isinstance(payload, bytes):
            text = payload.decode(
                "utf-8",
                errors="replace",
            )
        else:
            text = payload

        if not isinstance(text, str):
            raise TypeError("payload must be str or bytes.")

        fields = self._parse_fields(text)

        if not fields:
            raise ValueError(
                "No telemetry fields were found in the payload."
            )

        active_timestamp = timestamp or datetime.now(
            timezone.utc
        )

        if active_timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware."
            )

        return TelemetryPacket(
            satellite=satellite,
            fields=tuple(fields),
            timestamp=active_timestamp,
            source=source,
            sequence=sequence,
        )

    def _parse_fields(
        self,
        payload: str,
    ) -> list[TelemetryField]:
        """Extract key/value telemetry fields."""
        fields: list[TelemetryField] = []

        for match in self._TOKEN_PATTERN.finditer(payload):
            name = match.group("name")
            raw_value = match.group("value")

            value, unit = self._convert_value(raw_value)

            fields.append(
                TelemetryField(
                    name=name,
                    value=value,
                    raw_value=raw_value,
                    unit=unit,
                )
            )

        return fields

    @staticmethod
    def _convert_value(
        raw_value: str,
    ) -> tuple[Any, str | None]:
        """
        Convert a raw telemetry token to a useful Python value.

        Examples:

            "24.5"   -> 24.5
            "7"      -> 7
            "true"   -> True
            "SAFE"   -> "SAFE"
            "24.5C"  -> 24.5, "C"
        """
        normalized = raw_value.strip()

        lowered = normalized.lower()

        if lowered in {"true", "false"}:
            return lowered == "true", None

        if lowered in {"on", "off"}:
            return lowered == "on", None

        numeric_match = re.fullmatch(
            r"([+-]?\d+(?:\.\d+)?)([A-Za-z%°]+)?",
            normalized,
        )

        if numeric_match:
            number_text = numeric_match.group(1)
            unit = numeric_match.group(2)

            if "." in number_text:
                return float(number_text), unit

            return int(number_text), unit

        return normalized, None


def fields_from_mapping(
    values: dict[str, Any],
) -> tuple[TelemetryField, ...]:
    """
    Convert a mapping into telemetry fields.

    Useful when a binary mission-specific decoder has already
    extracted typed values.
    """
    result: list[TelemetryField] = []

    for name, value in values.items():
        result.append(
            TelemetryField(
                name=str(name),
                value=value,
                raw_value=str(value),
            )
        )

    return tuple(result)
