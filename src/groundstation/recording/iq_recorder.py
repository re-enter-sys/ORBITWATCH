from __future__ import annotations

import hashlib
import json
import struct
import uuid
from pathlib import Path
from typing import Iterable

from .models import IQChunk, RecordingMetadata, RecordingType, utc_now


MAGIC = b"ORBITIQ1"
HEADER_STRUCT = struct.Struct("<8sI")
SAMPLE_STRUCT = struct.Struct("<ff")


class IQRecordingWriter:
    """Writes complex64 IQ samples to an OrbitWatch recording."""

    def __init__(
        self,
        directory: str | Path,
        *,
        sample_rate_hz: float,
        center_frequency_hz: float,
        satellite: str | None = None,
        description: str = "",
        recording_id: str | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.recording_id = recording_id or self._generate_id()
        self.sample_rate_hz = float(sample_rate_hz)
        self.center_frequency_hz = float(center_frequency_hz)
        self.satellite = satellite
        self.description = description

        self.data_path = self.directory / f"{self.recording_id}.iq"
        self.metadata_path = self.directory / f"{self.recording_id}.json"

        self._file = None
        self._hash = hashlib.sha256()
        self._sample_count = 0
        self._started_at: str | None = None
        self._closed = False

    @staticmethod
    def _generate_id() -> str:
        timestamp = utc_now().replace(":", "").replace("-", "").replace("+00:00", "Z")
        return f"iq-{timestamp}-{uuid.uuid4().hex[:8]}"

    def start(self) -> RecordingMetadata:
        if self._file is not None:
            raise RuntimeError("Recording has already started.")

        self._started_at = utc_now()
        self._file = self.data_path.open("wb")

        header = HEADER_STRUCT.pack(MAGIC, 1)
        self._file.write(header)
        self._hash.update(header)

        return self.metadata()

    def write(self, samples: Iterable[complex]) -> int:
        if self._file is None:
            raise RuntimeError("Recording has not started.")
        if self._closed:
            raise RuntimeError("Recording is closed.")

        count = 0

        for sample in samples:
            value = complex(sample)
            payload = SAMPLE_STRUCT.pack(
                float(value.real),
                float(value.imag),
            )
            self._file.write(payload)
            self._hash.update(payload)
            count += 1

        self._sample_count += count
        return count

    def write_chunk(self, chunk: IQChunk) -> int:
        if abs(chunk.sample_rate_hz - self.sample_rate_hz) > 1e-9:
            raise ValueError("IQ chunk sample rate does not match recording.")

        if abs(chunk.center_frequency_hz - self.center_frequency_hz) > 1e-6:
            raise ValueError("IQ chunk center frequency does not match recording.")

        return self.write(chunk.samples)

    def metadata(self) -> RecordingMetadata:
        duration = (
            self._sample_count / self.sample_rate_hz
            if self.sample_rate_hz > 0
            else 0.0
        )

        return RecordingMetadata(
            recording_id=self.recording_id,
            recording_type=RecordingType.IQ,
            created_at=self._started_at or utc_now(),
            sample_rate_hz=self.sample_rate_hz,
            center_frequency_hz=self.center_frequency_hz,
            satellite=self.satellite,
            duration_seconds=duration,
            sample_count=self._sample_count,
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
            raise RuntimeError("Recording has not started.")

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

    def __enter__(self) -> "IQRecordingWriter":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if not self._closed:
            self.close()
