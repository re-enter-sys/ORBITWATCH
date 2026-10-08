from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MissionEventType(str, Enum):
    """Supported OrbitWatch mission events."""

    MISSION_STARTED = "mission_started"
    MISSION_STOPPED = "mission_stopped"

    SATELLITE_ACQUIRED = "satellite_acquired"
    SATELLITE_LOST = "satellite_lost"

    PASS_STARTED = "pass_started"
    PASS_ENDED = "pass_ended"

    SDR_CONNECTED = "sdr_connected"
    SDR_DISCONNECTED = "sdr_disconnected"
    SDR_ERROR = "sdr_error"

    SIGNAL_DETECTED = "signal_detected"
    SIGNAL_LOST = "signal_lost"

    PACKET_RECEIVED = "packet_received"
    PACKET_REJECTED = "packet_rejected"
    CRC_ERROR = "crc_error"

    TELEMETRY_RECEIVED = "telemetry_received"
    TELEMETRY_DECODE_ERROR = "telemetry_decode_error"

    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"

    REPLAY_STARTED = "replay_started"
    REPLAY_PAUSED = "replay_paused"
    REPLAY_RESUMED = "replay_resumed"
    REPLAY_STOPPED = "replay_stopped"
    REPLAY_COMPLETED = "replay_completed"

    SYSTEM_WARNING = "system_warning"
    SYSTEM_ERROR = "system_error"

    CUSTOM = "custom"


class MissionEventSeverity(str, Enum):
    """Severity classification for mission events."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MissionEvent:
    """
    Immutable representation of one operational event.

    Every event has a UTC timestamp and a structured payload so that
    mission history can be searched and consumed by the dashboard.
    """

    event_id: str
    timestamp: str
    event_type: MissionEventType
    severity: MissionEventSeverity
    message: str

    mission_id: str | None = None
    satellite: str | None = None
    recording_id: str | None = None
    packet_id: str | None = None

    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "mission_id": self.mission_id,
            "satellite": self.satellite,
            "recording_id": self.recording_id,
            "packet_id": self.packet_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MissionEvent":
        return cls(
            event_id=str(data["event_id"]),
            timestamp=str(data["timestamp"]),
            event_type=MissionEventType(str(data["event_type"])),
            severity=MissionEventSeverity(str(data["severity"])),
            message=str(data["message"]),
            mission_id=data.get("mission_id"),
            satellite=data.get("satellite"),
            recording_id=data.get("recording_id"),
            packet_id=data.get("packet_id"),
            payload=dict(data.get("payload", {})),
        )


@dataclass(frozen=True)
class MissionSession:
    """Represents one OrbitWatch operating session."""

    mission_id: str
    started_at: str
    ended_at: str | None = None

    satellite: str | None = None
    mode: str = "unknown"

    event_count: int = 0
    packet_count: int = 0
    telemetry_count: int = 0
    error_count: int = 0

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.ended_at is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "satellite": self.satellite,
            "mode": self.mode,
            "event_count": self.event_count,
            "packet_count": self.packet_count,
            "telemetry_count": self.telemetry_count,
            "error_count": self.error_count,
            "active": self.active,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class MissionStatistics:
    """Aggregated mission-log statistics."""

    total_events: int = 0
    information_events: int = 0
    success_events: int = 0
    warning_events: int = 0
    error_events: int = 0

    packet_events: int = 0
    telemetry_events: int = 0
    crc_errors: int = 0

    recordings_started: int = 0
    replays_completed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_events": self.total_events,
            "information_events": self.information_events,
            "success_events": self.success_events,
            "warning_events": self.warning_events,
            "error_events": self.error_events,
            "packet_events": self.packet_events,
            "telemetry_events": self.telemetry_events,
            "crc_errors": self.crc_errors,
            "recordings_started": self.recordings_started,
            "replays_completed": self.replays_completed,
        }
