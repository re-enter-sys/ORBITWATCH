"""
Telemetry integration engine for OrbitWatch.

Connects protocol-decoded payloads to the generic telemetry model,
mission-specific decoder registry, and persistent telemetry database.

Processing flow:

    KISS/AX.25 payload
          |
          v
    TelemetryParser
          |
          v
    TelemetryRecord
          |
          v
    TelemetryDecoderRegistry
          |
          v
    DecodedTelemetry
          |
          v
    TelemetryDatabase
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ..protocols.ax25 import AX25Frame
from ..protocols.kiss import KISSFrame
from .database import TelemetryDatabase
from .decoder import (
    DecodedTelemetry,
    TelemetryDecoderRegistry,
)
from .parser import (
    TelemetryRecord,
    parse_json,
    parse_key_value,
    parse_mapping,
)


@dataclass(frozen=True, slots=True)
class TelemetryProcessResult:
    """
    Result of processing one telemetry payload.

    The original record, decoded telemetry, and optional database
    identifier are retained so callers can inspect every stage.
    """

    record: TelemetryRecord
    decoded: DecodedTelemetry
    database_id: int | None = None

    @property
    def satellite(self) -> str:
        """Return the satellite identifier."""

        return self.record.satellite

    @property
    def timestamp(self) -> datetime:
        """Return the telemetry timestamp."""

        return self.record.timestamp

    @property
    def valid(self) -> bool:
        """Return whether the source record is valid."""

        return self.record.valid

    @property
    def crc_ok(self) -> bool | None:
        """Return the source CRC state."""

        return self.record.crc_ok

    @property
    def field_count(self) -> int:
        """Return the number of decoded telemetry fields."""

        return len(self.decoded.values)

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """Return one decoded telemetry value."""

        return self.decoded.get(name, default)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the processing result."""

        result = self.decoded.to_dict()
        result["database_id"] = self.database_id
        return result


class TelemetryEngine:
    """
    High-level telemetry processing engine.

    Responsibilities:

    - parse generic telemetry payloads
    - construct TelemetryRecord objects
    - apply registered mission decoders
    - optionally persist telemetry
    - process AX.25 frames
    - process KISS data frames
    """

    def __init__(
        self,
        *,
        registry: TelemetryDecoderRegistry | None = None,
        database: TelemetryDatabase | None = None,
        persist: bool = True,
    ) -> None:
        if registry is not None and not isinstance(
            registry,
            TelemetryDecoderRegistry,
        ):
            raise TypeError(
                "registry must be a TelemetryDecoderRegistry."
            )

        if database is not None and not isinstance(
            database,
            TelemetryDatabase,
        ):
            raise TypeError(
                "database must be a TelemetryDatabase."
            )

        self.registry = registry or TelemetryDecoderRegistry()
        self.database = database
        self.persist = bool(persist)

        if self.persist and self.database is None:
            self.database = TelemetryDatabase()

        self._processed_count = 0
        self._successful_count = 0
        self._failed_count = 0

    @property
    def processed_count(self) -> int:
        """Return the number of successfully processed records."""

        return self._processed_count

    @property
    def successful_count(self) -> int:
        """Return the number of successful processing operations."""

        return self._successful_count

    @property
    def failed_count(self) -> int:
        """Return the number of failed processing operations."""

        return self._failed_count

    def process_record(
        self,
        record: TelemetryRecord,
        *,
        persist: bool | None = None,
    ) -> TelemetryProcessResult:
        """
        Decode and optionally persist an existing telemetry record.
        """

        if not isinstance(record, TelemetryRecord):
            raise TypeError(
                "record must be a TelemetryRecord."
            )

        decoded = self.registry.decode(record)

        should_persist = (
            self.persist
            if persist is None
            else bool(persist)
        )

        database_id: int | None = None

        if should_persist:
            if self.database is None:
                raise RuntimeError(
                    "Telemetry persistence is enabled but no database "
                    "is configured."
                )

            database_id = self.database.insert(record)

        self._processed_count += 1
        self._successful_count += 1

        return TelemetryProcessResult(
            record=record,
            decoded=decoded,
            database_id=database_id,
        )

    def process_mapping(
        self,
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
        persist: bool | None = None,
    ) -> TelemetryProcessResult:
        """Parse and process mapping telemetry."""

        record = parse_mapping(
            payload,
            satellite=satellite,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            raw_payload=raw_payload,
            metadata=metadata,
        )

        return self.process_record(
            record,
            persist=persist,
        )

    def process_json(
        self,
        payload: str | bytes,
        *,
        satellite: str,
        timestamp: datetime | None = None,
        source: str = "json",
        packet_id: str | None = None,
        valid: bool = True,
        crc_ok: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
        persist: bool | None = None,
    ) -> TelemetryProcessResult:
        """Parse and process JSON telemetry."""

        record = parse_json(
            payload,
            satellite=satellite,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            metadata=metadata,
        )

        return self.process_record(
            record,
            persist=persist,
        )

    def process_key_value(
        self,
        payload: str | bytes,
        *,
        satellite: str,
        timestamp: datetime | None = None,
        source: str = "key_value",
        packet_id: str | None = None,
        valid: bool = True,
        crc_ok: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
        persist: bool | None = None,
    ) -> TelemetryProcessResult:
        """Parse and process key/value telemetry."""

        record = parse_key_value(
            payload,
            satellite=satellite,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            metadata=metadata,
        )

        return self.process_record(
            record,
            persist=persist,
        )

    def process_ax25(
        self,
        frame: AX25Frame,
        *,
        satellite: str | None = None,
        timestamp: datetime | None = None,
        source: str = "ax25",
        packet_id: str | None = None,
        valid: bool = True,
        crc_ok: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
        persist: bool | None = None,
    ) -> TelemetryProcessResult:
        """
        Extract telemetry from an AX.25 frame.

        The AX.25 source callsign is used as the default satellite
        identifier when one is not explicitly supplied.
        """

        if not isinstance(frame, AX25Frame):
            raise TypeError(
                "frame must be an AX25Frame."
            )

        if not frame.is_ui_frame:
            raise ValueError(
                "Only AX.25 UI frames can carry generic telemetry."
            )

        satellite_name = (
            satellite.strip()
            if satellite is not None
            else frame.source.display
        )

        if not satellite_name:
            raise ValueError(
                "A satellite identifier is required."
            )

        frame_metadata = dict(metadata or {})

        frame_metadata.setdefault(
            "ax25_source",
            frame.source.display,
        )
        frame_metadata.setdefault(
            "ax25_destination",
            frame.destination.display,
        )
        frame_metadata.setdefault(
            "ax25_path",
            list(frame.path),
        )
        frame_metadata.setdefault(
            "ax25_control",
            frame.control,
        )
        frame_metadata.setdefault(
            "ax25_pid",
            frame.pid,
        )

        return self.process_key_value(
            frame.information,
            satellite=satellite_name,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            metadata=frame_metadata,
            persist=persist,
        )

    def process_kiss(
        self,
        frame: KISSFrame,
        *,
        satellite: str | None = None,
        timestamp: datetime | None = None,
        source: str = "kiss",
        packet_id: str | None = None,
        valid: bool = True,
        crc_ok: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
        persist: bool | None = None,
    ) -> TelemetryProcessResult:
        """
        Process a KISS data frame containing an AX.25 frame.
        """

        if not isinstance(frame, KISSFrame):
            raise TypeError(
                "frame must be a KISSFrame."
            )

        if not frame.is_data:
            raise ValueError(
                "Only KISS data frames can carry AX.25 telemetry."
            )

        from ..protocols.ax25 import AX25Parser

        ax25_frame = AX25Parser().parse(frame.payload)

        frame_metadata = dict(metadata or {})
        frame_metadata.setdefault(
            "kiss_command",
            frame.command,
        )

        return self.process_ax25(
            ax25_frame,
            satellite=satellite,
            timestamp=timestamp,
            source=source,
            packet_id=packet_id,
            valid=valid,
            crc_ok=crc_ok,
            metadata=frame_metadata,
            persist=persist,
        )

    def process_records(
        self,
        records: Iterable[TelemetryRecord],
        *,
        persist: bool | None = None,
    ) -> list[TelemetryProcessResult]:
        """Process multiple telemetry records."""

        results: list[TelemetryProcessResult] = []

        for record in records:
            results.append(
                self.process_record(
                    record,
                    persist=persist,
                )
            )

        return results

    def statistics(self) -> dict[str, int]:
        """Return engine processing statistics."""

        return {
            "processed": self._processed_count,
            "successful": self._successful_count,
            "failed": self._failed_count,
        }

    def reset_statistics(self) -> None:
        """Reset processing counters."""

        self._processed_count = 0
        self._successful_count = 0
        self._failed_count = 0

    def close(self) -> None:
        """Close the configured telemetry database."""

        if self.database is not None:
            self.database.close()

    def __enter__(self) -> "TelemetryEngine":
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()
