"""
Telemetry decoding engine for OrbitWatch.

The parser converts raw telemetry into a generic TelemetryRecord.

The decoder layer adds mission-specific interpretation without coupling
the parser to any particular satellite.

Example:

    TEMP=24.5,BATT=7.4

can become:

    temperature = 24.5 C
    battery_voltage = 7.4 V

Mission decoders can be registered by satellite name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from .parser import (
    TelemetryRecord,
    TelemetryValue,
    infer_data_type,
    normalize_field_name,
)


@dataclass(frozen=True, slots=True)
class DecodedTelemetry:
    """
    Result of decoding one telemetry record.

    The original record is preserved so the system never loses the
    original telemetry information.
    """

    record: TelemetryRecord
    values: dict[str, TelemetryValue] = field(default_factory=dict)
    decoder: str = "generic"
    warnings: tuple[str, ...] = ()

    @property
    def satellite(self) -> str:
        """Return the satellite name."""

        return self.record.satellite

    @property
    def timestamp(self):
        """Return the telemetry timestamp."""

        return self.record.timestamp

    @property
    def valid(self) -> bool:
        """Return the original telemetry validity."""

        return self.record.valid

    @property
    def crc_ok(self) -> bool | None:
        """Return the original CRC state."""

        return self.record.crc_ok

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """Return a decoded value."""

        normalized = normalize_field_name(name)

        value = self.values.get(normalized)

        if value is None:
            return default

        return value.value

    def as_dict(self) -> dict[str, Any]:
        """Return decoded values as a simple mapping."""

        return {
            name: value.value
            for name, value in self.values.items()
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decoded telemetry."""

        return {
            "satellite": self.record.satellite,
            "timestamp": self.record.timestamp.isoformat(),
            "source": self.record.source,
            "packet_id": self.record.packet_id,
            "valid": self.record.valid,
            "crc_ok": self.record.crc_ok,
            "decoder": self.decoder,
            "warnings": list(self.warnings),
            "values": {
                name: value.to_dict()
                for name, value in self.values.items()
            },
        }


DecoderFunction = Callable[
    [TelemetryRecord],
    Mapping[str, Any] | Iterable[TelemetryValue],
]


class TelemetryDecoder:
    """
    Generic telemetry decoder.

    A decoder can optionally contain a custom callable. If no callable
    is supplied, the telemetry record is normalized and returned as-is.
    """

    def __init__(
        self,
        name: str = "generic",
        decoder: DecoderFunction | None = None,
    ) -> None:
        if not name.strip():
            raise ValueError("Decoder name cannot be empty.")

        self.name = name
        self._decoder = decoder

    def decode(
        self,
        record: TelemetryRecord,
    ) -> DecodedTelemetry:
        """
        Decode one telemetry record.
        """

        if not isinstance(record, TelemetryRecord):
            raise TypeError(
                "decoder expects a TelemetryRecord."
            )

        if self._decoder is None:
            values = dict(record.values)
            warnings: tuple[str, ...] = ()
        else:
            decoded = self._decoder(record)
            values = self._normalize_decoded_values(decoded)
            warnings = ()

        return DecodedTelemetry(
            record=record,
            values=values,
            decoder=self.name,
            warnings=warnings,
        )

    @staticmethod
    def _normalize_decoded_values(
        decoded: Mapping[str, Any] | Iterable[TelemetryValue],
    ) -> dict[str, TelemetryValue]:
        """
        Normalize decoder output into TelemetryValue objects.
        """

        if isinstance(decoded, Mapping):
            result: dict[str, TelemetryValue] = {}

            for name, value in decoded.items():
                normalized_name = normalize_field_name(name)

                if not normalized_name:
                    continue

                if isinstance(value, TelemetryValue):
                    result[normalized_name] = TelemetryValue(
                        name=normalized_name,
                        value=value.value,
                        unit=value.unit,
                        data_type=value.data_type,
                        raw_value=value.raw_value,
                    )
                    continue

                unit = None
                actual_value = value

                if isinstance(value, Mapping):
                    unit = value.get("unit")
                    actual_value = value.get(
                        "value",
                        value.get("data"),
                    )

                result[normalized_name] = TelemetryValue(
                    name=normalized_name,
                    value=actual_value,
                    unit=unit,
                    data_type=infer_data_type(actual_value),
                    raw_value=str(actual_value),
                )

            return result

        result = {}

        for value in decoded:
            if not isinstance(value, TelemetryValue):
                raise TypeError(
                    "Iterable decoder output must contain "
                    "TelemetryValue objects."
                )

            normalized_name = normalize_field_name(
                value.name
            )

            if not normalized_name:
                continue

            result[normalized_name] = TelemetryValue(
                name=normalized_name,
                value=value.value,
                unit=value.unit,
                data_type=value.data_type,
                raw_value=value.raw_value,
            )

        return result


class TelemetryDecoderRegistry:
    """
    Registry of satellite-specific telemetry decoders.

    Satellite matching is case-insensitive.
    """

    def __init__(self) -> None:
        self._decoders: dict[str, TelemetryDecoder] = {}
        self._default = TelemetryDecoder()

    @staticmethod
    def _normalize_satellite(
        satellite: str,
    ) -> str:
        normalized = str(satellite).strip().upper()

        if not normalized:
            raise ValueError(
                "Satellite name cannot be empty."
            )

        return normalized

    def register(
        self,
        satellite: str,
        decoder: TelemetryDecoder,
    ) -> None:
        """Register or replace a satellite decoder."""

        if not isinstance(decoder, TelemetryDecoder):
            raise TypeError(
                "decoder must be a TelemetryDecoder."
            )

        key = self._normalize_satellite(satellite)
        self._decoders[key] = decoder

    def unregister(
        self,
        satellite: str,
    ) -> bool:
        """Remove a satellite decoder."""

        key = self._normalize_satellite(satellite)

        return self._decoders.pop(
            key,
            None,
        ) is not None

    def get(
        self,
        satellite: str,
    ) -> TelemetryDecoder:
        """Return the satellite decoder or generic fallback."""

        key = self._normalize_satellite(satellite)

        return self._decoders.get(
            key,
            self._default,
        )

    def decode(
        self,
        record: TelemetryRecord,
    ) -> DecodedTelemetry:
        """Decode a telemetry record using the best decoder."""

        if not isinstance(record, TelemetryRecord):
            raise TypeError(
                "record must be a TelemetryRecord."
            )

        decoder = self.get(record.satellite)

        return decoder.decode(record)

    def satellites(self) -> tuple[str, ...]:
        """Return registered satellite names."""

        return tuple(sorted(self._decoders))

    def clear(self) -> None:
        """Remove all registered decoders."""

        self._decoders.clear()
