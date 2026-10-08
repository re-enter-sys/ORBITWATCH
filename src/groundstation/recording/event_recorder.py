from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Iterable

from .models import RecordingEvent, RecordingMetadata, RecordingType, utc_now


class EventRecordingWriter:
    """Stores decoded telemetry and packet events as JSONL."""

    def __init__(
        self,
        directory: str | Path,
        *,
        satellite: str | None = None,
        description: str = "",
        recording_id: str | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.recording_id = recording_id or self._generate_id()
        self.satellite = satellite
        self.description = description

        self.data_path = self.directory / f"{self.recording_id}.jsonl"
        self.metadata_path = self.directory / f"{self.recording_id}.json"

        self._file = None
        self._hash = hashlib.sha256()
        self._event_count = 0
        self._started_at: str | None = None
        self._closed = False

    @staticmethod
    def _generate_id() -> str:
        timestamp = utc_now().replace(":", "").replace("-", "").replace("+00:00", "Z")
        return f"events-{timestamp}-{uuid.uuid4().hex[:8]}"

    def start(self) -> RecordingMetadata:
        if self._file is not None:
            raise RuntimeError("Event recording has already started.")

        self._started_at = utc_now()
        self._file = self.data_path.open("w", encoding="utf-8")
        return self.metadata()

    def write(self, event: RecordingEvent) -> None:
        if self._file is None:
            raise RuntimeError("Event recording has not started.")
        if self._closed:
            raise RuntimeError("Event recording is closed.")

        line = json.dumps(event.to_dict(), separators=(",", ":")) + "\n"
        encoded = line.encode("utf-8")

        self._file.write(line)
        self._hash.update(encoded)
        self._event_count += 1

    def write_mapping(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        timestamp: str | None = None,
    ) -> RecordingEvent:
        event = RecordingEvent(
            timestamp=timestamp or utc_now(),
            event_type=event_type,
            payload=dict(payload),
        )
        self.write(event)
        return event

    def write_many(self, events: Iterable[RecordingEvent]) -> int:
        count = 0

        for event in events:
            self.write(event)
            count += 1

        return count

    def metadata(self) -> RecordingMetadata:
        return RecordingMetadata(
            recording_id=self.recording_id,
            recording_type=RecordingType.EVENTS,
            created_at=self._started_at or utc_now(),
            satellite=self.satellite,
            event_count=self._event_count,
            source="orbitwatch",
            description=self.description,
            sha256=self._hash.hexdigest(),
        )

    def close(self) -> RecordingMetadata:
        if self._closed:
            return RecordingMetadata.from_dict(
                json.loads(self.metadata_path.read_text())
            )

        if self._file is None:
            raise RuntimeError("Event recording has not started.")

        metadata = self.metadata()

        self._file.flush()
        self._file.close()
        self._file = None
        self._closed = True

        self.metadata_path.write_text(
            json.dumps(metadata.to_dict(), indent=2),
            encoding="utf-8",
        )

        return metadata

    def __enter__(self) -> "EventRecordingWriter":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if not self._closed:
            self.close()
