from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Iterator

from .iq_recorder import HEADER_STRUCT, MAGIC, SAMPLE_STRUCT
from .models import IQChunk, RecordingEvent, RecordingMetadata


class RecordingError(Exception):
    """Base exception for invalid OrbitWatch recordings."""


class RecordingIntegrityError(RecordingError):
    """Raised when a recording fails integrity validation."""


class IQRecordingReader:
    """Reads OrbitWatch complex64 IQ recordings."""

    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)

        if not self.data_path.exists():
            raise FileNotFoundError(self.data_path)

        self.metadata_path = self.data_path.with_suffix(".json")

        if not self.metadata_path.exists():
            raise RecordingError(
                f"Missing metadata file: {self.metadata_path}"
            )

        self._metadata = RecordingMetadata.from_dict(
            json.loads(self.metadata_path.read_text(encoding="utf-8"))
        )

    @property
    def metadata(self) -> RecordingMetadata:
        return self._metadata

    def validate(self) -> bool:
        digest = hashlib.sha256()

        with self.data_path.open("rb") as file:
            header = file.read(HEADER_STRUCT.size)

            if len(header) != HEADER_STRUCT.size:
                raise RecordingIntegrityError("Recording header is truncated.")

            magic, version = HEADER_STRUCT.unpack(header)

            if magic != MAGIC:
                raise RecordingIntegrityError("Invalid OrbitWatch IQ magic.")

            if version != 1:
                raise RecordingIntegrityError(
                    f"Unsupported IQ recording version: {version}"
                )

            digest.update(header)

            payload = file.read()

            if len(payload) % SAMPLE_STRUCT.size != 0:
                raise RecordingIntegrityError(
                    "IQ recording contains a truncated sample."
                )

            digest.update(payload)

        expected = self.metadata.sha256

        if expected and digest.hexdigest() != expected:
            raise RecordingIntegrityError(
                "IQ recording SHA-256 checksum does not match metadata."
            )

        actual_samples = (
            (self.data_path.stat().st_size - HEADER_STRUCT.size)
            // SAMPLE_STRUCT.size
        )

        if actual_samples != self.metadata.sample_count:
            raise RecordingIntegrityError(
                "IQ sample count does not match metadata."
            )

        return True

    def iter_samples(self, chunk_size: int = 4096) -> Iterator[tuple[complex, ...]]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        with self.data_path.open("rb") as file:
            header = file.read(HEADER_STRUCT.size)

            if len(header) != HEADER_STRUCT.size:
                raise RecordingIntegrityError("Recording header is truncated.")

            magic, version = HEADER_STRUCT.unpack(header)

            if magic != MAGIC or version != 1:
                raise RecordingIntegrityError("Invalid IQ recording header.")

            while True:
                samples: list[complex] = []

                for _ in range(chunk_size):
                    payload = file.read(SAMPLE_STRUCT.size)

                    if not payload:
                        break

                    if len(payload) != SAMPLE_STRUCT.size:
                        raise RecordingIntegrityError(
                            "IQ recording contains a truncated sample."
                        )

                    real, imaginary = SAMPLE_STRUCT.unpack(payload)
                    samples.append(complex(real, imaginary))

                if not samples:
                    break

                yield tuple(samples)

    def iter_chunks(self, chunk_size: int = 4096) -> Iterator[IQChunk]:
        for samples in self.iter_samples(chunk_size):
            yield IQChunk(
                samples=samples,
                sample_rate_hz=self.metadata.sample_rate_hz or 0.0,
                center_frequency_hz=self.metadata.center_frequency_hz or 0.0,
                timestamp=self.metadata.created_at,
            )


class EventRecordingReader:
    """Reads OrbitWatch JSONL event recordings."""

    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)

        if not self.data_path.exists():
            raise FileNotFoundError(self.data_path)

        self.metadata_path = self.data_path.with_suffix(".json")

        if not self.metadata_path.exists():
            raise RecordingError(
                f"Missing metadata file: {self.metadata_path}"
            )

        self._metadata = RecordingMetadata.from_dict(
            json.loads(self.metadata_path.read_text(encoding="utf-8"))
        )

    @property
    def metadata(self) -> RecordingMetadata:
        return self._metadata

    def iter_events(self) -> Iterator[RecordingEvent]:
        with self.data_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    data = json.loads(line)
                    yield RecordingEvent.from_dict(data)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RecordingError(
                        f"Invalid event at line {line_number}: {exc}"
                    ) from exc

    def validate(self) -> bool:
        digest = hashlib.sha256()
        count = 0

        with self.data_path.open("rb") as file:
            for raw_line in file:
                if not raw_line.strip():
                    continue

                digest.update(raw_line)
                count += 1

                try:
                    data = json.loads(raw_line.decode("utf-8"))
                    RecordingEvent.from_dict(data)
                except Exception as exc:
                    raise RecordingIntegrityError(
                        f"Invalid event at line {count}: {exc}"
                    ) from exc

        if count != self.metadata.event_count:
            raise RecordingIntegrityError(
                "Event count does not match metadata."
            )

        expected = self.metadata.sha256

        if expected and digest.hexdigest() != expected:
            raise RecordingIntegrityError(
                "Event recording SHA-256 checksum does not match metadata."
            )

        return True
