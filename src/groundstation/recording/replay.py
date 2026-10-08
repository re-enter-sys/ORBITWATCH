from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .models import (
    IQChunk,
    RecordingEvent,
    ReplayState,
    ReplayStatistics,
)


@dataclass(frozen=True)
class ReplayStatus:
    state: ReplayState
    speed: float
    progress: float
    statistics: ReplayStatistics

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "speed": self.speed,
            "progress": self.progress,
            "statistics": self.statistics.to_dict(),
        }


class ReplayController:
    """
    Deterministic replay controller.

    The controller deliberately separates timing from processing so that
    tests and development environments can run replay at unlimited speed.
    """

    def __init__(
        self,
        *,
        speed: float = 1.0,
        realtime: bool = False,
    ) -> None:
        if speed <= 0:
            raise ValueError("speed must be greater than zero.")

        self._speed = float(speed)
        self._realtime = bool(realtime)
        self._state = ReplayState.IDLE
        self._progress = 0.0
        self._statistics = ReplayStatistics()

        self._pause_event = threading.Event()
        self._stop_event = threading.Event()

    @property
    def state(self) -> ReplayState:
        return self._state

    @property
    def speed(self) -> float:
        return self._speed

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be greater than zero.")

        self._speed = float(speed)

    def pause(self) -> None:
        if self._state == ReplayState.PLAYING:
            self._state = ReplayState.PAUSED
            self._pause_event.set()

    def resume(self) -> None:
        if self._state == ReplayState.PAUSED:
            self._state = ReplayState.PLAYING
            self._pause_event.clear()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.clear()

        if self._state in {
            ReplayState.PLAYING,
            ReplayState.PAUSED,
            ReplayState.READY,
        }:
            self._state = ReplayState.STOPPED

    def reset(self) -> None:
        self._stop_event.clear()
        self._pause_event.clear()
        self._state = ReplayState.IDLE
        self._progress = 0.0
        self._statistics = ReplayStatistics()

    def status(self) -> ReplayStatus:
        return ReplayStatus(
            state=self._state,
            speed=self._speed,
            progress=self._progress,
            statistics=self._statistics,
        )

    def replay_iq(
        self,
        chunks: Iterable[IQChunk],
        callback: Callable[[IQChunk], None],
        *,
        total_samples: int | None = None,
    ) -> ReplayStatus:
        self.reset()
        self._state = ReplayState.READY

        start_time = time.monotonic()

        try:
            for chunk in chunks:
                if self._stop_event.is_set():
                    self._state = ReplayState.STOPPED
                    break

                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        self._state = ReplayState.STOPPED
                        return self.status()

                    time.sleep(0.01)

                self._state = ReplayState.PLAYING

                callback(chunk)

                self._statistics.chunks_processed += 1
                self._statistics.samples_processed += chunk.sample_count

                if total_samples and total_samples > 0:
                    self._progress = min(
                        1.0,
                        self._statistics.samples_processed / total_samples,
                    )

                if self._realtime and chunk.sample_rate_hz > 0:
                    duration = chunk.sample_count / chunk.sample_rate_hz
                    time.sleep(duration / self._speed)

            if self._state != ReplayState.STOPPED:
                self._progress = 1.0
                self._state = ReplayState.COMPLETED

        except Exception:
            self._state = ReplayState.ERROR
            raise

        finally:
            self._statistics.elapsed_seconds = time.monotonic() - start_time

        return self.status()

    def replay_events(
        self,
        events: Iterable[RecordingEvent],
        callback: Callable[[RecordingEvent], None],
    ) -> ReplayStatus:
        self.reset()
        self._state = ReplayState.READY

        previous_timestamp: float | None = None
        start_time = time.monotonic()

        try:
            for event in events:
                if self._stop_event.is_set():
                    self._state = ReplayState.STOPPED
                    break

                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        self._state = ReplayState.STOPPED
                        return self.status()

                    time.sleep(0.01)

                self._state = ReplayState.PLAYING

                if self._realtime:
                    timestamp = _parse_timestamp(event.timestamp)

                    if timestamp is not None and previous_timestamp is not None:
                        delay = max(0.0, timestamp - previous_timestamp)
                        time.sleep(delay / self._speed)

                    if timestamp is not None:
                        previous_timestamp = timestamp

                callback(event)

                self._statistics.events_processed += 1

            if self._state != ReplayState.STOPPED:
                self._progress = 1.0
                self._state = ReplayState.COMPLETED

        except Exception:
            self._state = ReplayState.ERROR
            raise

        finally:
            self._statistics.elapsed_seconds = time.monotonic() - start_time

        return self.status()


def _parse_timestamp(value: str) -> float | None:
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None
