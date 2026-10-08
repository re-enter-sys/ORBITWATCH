from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RecordingType(str, Enum):
    IQ = "iq"
    EVENTS = "events"
    SESSION = "session"


class ReplayState(str, Enum):
    IDLE = "idle"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RecordingMetadata:
    recording_id: str
    recording_type: RecordingType
    created_at: str
    sample_rate_hz: float | None = None
    center_frequency_hz: float | None = None
    satellite: str | None = None
    duration_seconds: float = 0.0
    sample_count: int = 0
    event_count: int = 0
    source: str = "orbitwatch"
    format_version: int = 1
    sha256: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "recording_id": self.recording_id,
            "recording_type": self.recording_type.value,
            "created_at": self.created_at,
            "sample_rate_hz": self.sample_rate_hz,
            "center_frequency_hz": self.center_frequency_hz,
            "satellite": self.satellite,
            "duration_seconds": self.duration_seconds,
            "sample_count": self.sample_count,
            "event_count": self.event_count,
            "source": self.source,
            "format_version": self.format_version,
            "sha256": self.sha256,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecordingMetadata":
        return cls(
            recording_id=str(data["recording_id"]),
            recording_type=RecordingType(str(data["recording_type"])),
            created_at=str(data["created_at"]),
            sample_rate_hz=(
                float(data["sample_rate_hz"])
                if data.get("sample_rate_hz") is not None
                else None
            ),
            center_frequency_hz=(
                float(data["center_frequency_hz"])
                if data.get("center_frequency_hz") is not None
                else None
            ),
            satellite=data.get("satellite"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            sample_count=int(data.get("sample_count", 0)),
            event_count=int(data.get("event_count", 0)),
            source=str(data.get("source", "orbitwatch")),
            format_version=int(data.get("format_version", 1)),
            sha256=data.get("sha256"),
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True)
class IQChunk:
    samples: tuple[complex, ...]
    sample_rate_hz: float
    center_frequency_hz: float
    timestamp: str

    @property
    def sample_count(self) -> int:
        return len(self.samples)


@dataclass(frozen=True)
class RecordingEvent:
    timestamp: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecordingEvent":
        return cls(
            timestamp=str(data["timestamp"]),
            event_type=str(data["event_type"]),
            payload=dict(data.get("payload", {})),
        )


@dataclass
class ReplayStatistics:
    chunks_processed: int = 0
    samples_processed: int = 0
    events_processed: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunks_processed": self.chunks_processed,
            "samples_processed": self.samples_processed,
            "events_processed": self.events_processed,
            "elapsed_seconds": self.elapsed_seconds,
        }
