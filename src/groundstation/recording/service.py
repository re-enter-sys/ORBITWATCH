from __future__ import annotations

from pathlib import Path
from typing import Any

from .event_recorder import EventRecordingWriter
from .iq_recorder import IQRecordingWriter
from .models import RecordingEvent, RecordingMetadata
from .reader import EventRecordingReader, IQRecordingReader
from .replay import ReplayController, ReplayStatus


class RecordingService:
    """
    High-level recording/replay facade used by OrbitWatch.

    It keeps recording storage separate from SDR and telemetry processing,
    making the subsystem usable in both real-RF and replay/development modes.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.iq_directory = self.root / "iq"
        self.events_directory = self.root / "events"

        self.iq_directory.mkdir(parents=True, exist_ok=True)
        self.events_directory.mkdir(parents=True, exist_ok=True)

    def start_iq_recording(
        self,
        *,
        sample_rate_hz: float,
        center_frequency_hz: float,
        satellite: str | None = None,
        description: str = "",
    ) -> IQRecordingWriter:
        writer = IQRecordingWriter(
            self.iq_directory,
            sample_rate_hz=sample_rate_hz,
            center_frequency_hz=center_frequency_hz,
            satellite=satellite,
            description=description,
        )
        writer.start()
        return writer

    def start_event_recording(
        self,
        *,
        satellite: str | None = None,
        description: str = "",
    ) -> EventRecordingWriter:
        writer = EventRecordingWriter(
            self.events_directory,
            satellite=satellite,
            description=description,
        )
        writer.start()
        return writer

    def list_recordings(self) -> list[RecordingMetadata]:
        recordings: list[RecordingMetadata] = []

        for metadata_path in sorted(self.root.rglob("*.json")):
            try:
                metadata = RecordingMetadata.from_dict(
                    __import__("json").loads(
                        metadata_path.read_text(encoding="utf-8")
                    )
                )
            except (OSError, ValueError, KeyError, TypeError):
                continue

            recordings.append(metadata)

        recordings.sort(
            key=lambda item: item.created_at,
            reverse=True,
        )

        return recordings

    def inspect(self, recording_id: str) -> RecordingMetadata:
        for metadata in self.list_recordings():
            if metadata.recording_id == recording_id:
                return metadata

        raise FileNotFoundError(
            f"Recording not found: {recording_id}"
        )

    def validate(self, recording_id: str) -> bool:
        metadata = self.inspect(recording_id)

        if metadata.recording_type.value == "iq":
            reader = IQRecordingReader(
                self.iq_directory / f"{recording_id}.iq"
            )
            return reader.validate()

        if metadata.recording_type.value == "events":
            reader = EventRecordingReader(
                self.events_directory / f"{recording_id}.jsonl"
            )
            return reader.validate()

        raise ValueError(
            f"Unsupported recording type: {metadata.recording_type}"
        )

    def create_iq_replay(
        self,
        recording_id: str,
        *,
        speed: float = 1.0,
        realtime: bool = False,
    ) -> tuple[IQRecordingReader, ReplayController]:
        metadata = self.inspect(recording_id)

        if metadata.recording_type.value != "iq":
            raise ValueError("Recording is not an IQ recording.")

        reader = IQRecordingReader(
            self.iq_directory / f"{recording_id}.iq"
        )

        controller = ReplayController(
            speed=speed,
            realtime=realtime,
        )

        return reader, controller

    def create_event_replay(
        self,
        recording_id: str,
        *,
        speed: float = 1.0,
        realtime: bool = False,
    ) -> tuple[EventRecordingReader, ReplayController]:
        metadata = self.inspect(recording_id)

        if metadata.recording_type.value != "events":
            raise ValueError("Recording is not an event recording.")

        reader = EventRecordingReader(
            self.events_directory / f"{recording_id}.jsonl"
        )

        controller = ReplayController(
            speed=speed,
            realtime=realtime,
        )

        return reader, controller

    def status(self) -> dict[str, Any]:
        recordings = self.list_recordings()

        iq_count = sum(
            item.recording_type.value == "iq"
            for item in recordings
        )

        event_count = sum(
            item.recording_type.value == "events"
            for item in recordings
        )

        return {
            "recordings": len(recordings),
            "iq_recordings": iq_count,
            "event_recordings": event_count,
            "storage_path": str(self.root),
        }
