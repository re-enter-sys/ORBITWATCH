"""
Satellite pass prediction for OrbitWatch.

This module groups sampled orbital states into visible satellite passes
for a ground station.

The implementation is intentionally geometry-based and deterministic.
It does not perform precision SGP4 propagation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Iterable

from .orbit import (
    GroundStationLocation,
    OrbitalState,
    calculate_look_angles,
    ensure_utc,
)


class PassStatus(str, Enum):
    """Current status of a satellite pass."""

    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class PassEvent:
    """A predicted visible satellite pass."""

    satellite: str
    aos: datetime
    los: datetime
    max_elevation_deg: float
    aos_azimuth_deg: float
    los_azimuth_deg: float

    def __post_init__(self) -> None:
        satellite = str(self.satellite).strip()

        if not satellite:
            raise ValueError("satellite must not be empty")

        aos = ensure_utc(self.aos)
        los = ensure_utc(self.los)

        if los < aos:
            raise ValueError(
                "los must be greater than or equal to aos"
            )

        object.__setattr__(self, "satellite", satellite)
        object.__setattr__(self, "aos", aos)
        object.__setattr__(self, "los", los)

    @property
    def duration_seconds(self) -> float:
        """Return pass duration in seconds."""

        return max(
            0.0,
            (self.los - self.aos).total_seconds(),
        )

    @property
    def status(self) -> PassStatus:
        """Return the current pass status."""

        now = datetime.now(timezone.utc)

        if now < self.aos:
            return PassStatus.UPCOMING

        if now > self.los:
            return PassStatus.COMPLETED

        return PassStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        """Serialize the pass event to a JSON-compatible dictionary."""

        return {
            "satellite": self.satellite,
            "aos": self.aos.isoformat(),
            "los": self.los.isoformat(),
            "duration_seconds": self.duration_seconds,
            "max_elevation_deg": self.max_elevation_deg,
            "aos_azimuth_deg": self.aos_azimuth_deg,
            "los_azimuth_deg": self.los_azimuth_deg,
            "status": self.status.value,
        }


class PassPredictor:
    """Predict visible passes from sampled orbital states."""

    def __init__(
        self,
        station: GroundStationLocation,
        minimum_elevation_deg: float = 0.0,
    ) -> None:
        if not isinstance(station, GroundStationLocation):
            raise TypeError(
                "station must be a GroundStationLocation"
            )

        if not isinstance(
            minimum_elevation_deg,
            (int, float),
        ):
            raise TypeError(
                "minimum_elevation_deg must be numeric"
            )

        if not float("-inf") < float(
            minimum_elevation_deg
        ) < float("inf"):
            raise ValueError(
                "minimum_elevation_deg must be finite"
            )

        if minimum_elevation_deg < -90.0:
            raise ValueError(
                "minimum_elevation_deg must be >= -90"
            )

        if minimum_elevation_deg > 90.0:
            raise ValueError(
                "minimum_elevation_deg must be <= 90"
            )

        self.station = station
        self.minimum_elevation_deg = float(
            minimum_elevation_deg
        )

    def predict(
        self,
        states: Iterable[OrbitalState],
    ) -> list[PassEvent]:
        """
        Convert sampled orbital states into visible pass events.

        Consecutive visible samples are grouped into one pass.
        """

        ordered_states = list(states)

        if not ordered_states:
            return []

        for state in ordered_states:
            if not isinstance(state, OrbitalState):
                raise TypeError(
                    "states must contain OrbitalState objects"
                )

        ordered_states.sort(
            key=lambda state: state.timestamp
        )

        passes: list[PassEvent] = []
        visible_samples: list[tuple[OrbitalState, object]] = []

        for state in ordered_states:
            look = calculate_look_angles(
                state,
                self.station,
            )

            visible = (
                look.elevation_deg
                >= self.minimum_elevation_deg
            )

            if visible:
                visible_samples.append(
                    (state, look)
                )
                continue

            if visible_samples:
                passes.append(
                    self._build_event(
                        visible_samples,
                        previous_state=state,
                    )
                )

                visible_samples = []

        if visible_samples:
            first_visible_state = visible_samples[0][0]

            first_index = next(
                index
                for index, state in enumerate(
                    ordered_states
                )
                if state is first_visible_state
            )

            previous_state = (
                ordered_states[first_index - 1]
                if first_index > 0
                else None
            )

            passes.append(
                self._build_event(
                    visible_samples,
                    previous_state=previous_state,
                )
            )

        return passes

    def predict_from_provider(
        self,
        provider: Callable[[datetime], OrbitalState],
        start: datetime,
        duration_seconds: float | None = None,
        step_seconds: float = 30.0,
        *,
        duration_minutes: float | None = None,
    ) -> list[PassEvent]:
        """
        Generate sampled states from a provider and predict passes.

        ``provider`` receives a UTC timestamp and must return an
        ``OrbitalState``.
        """

        if not callable(provider):
            raise TypeError(
                "provider must be callable"
            )

        start = ensure_utc(start)

        if (
            duration_seconds is None
            and duration_minutes is not None
        ):
            duration_seconds = (
                float(duration_minutes) * 60.0
            )

        if duration_seconds is None:
            raise ValueError(
                "duration_seconds or duration_minutes "
                "must be provided"
            )

        duration_seconds = float(duration_seconds)
        step_seconds = float(step_seconds)

        if duration_seconds <= 0:
            raise ValueError(
                "duration_seconds must be > 0"
            )

        if step_seconds <= 0:
            raise ValueError(
                "step_seconds must be > 0"
            )

        states: list[OrbitalState] = []

        elapsed = 0.0

        while elapsed <= duration_seconds:
            timestamp = (
                start
                + timedelta(seconds=elapsed)
            )

            states.append(
                provider(timestamp)
            )

            elapsed += step_seconds

        return self.predict(states)

    def _build_event(
        self,
        visible_samples: list[
            tuple[OrbitalState, object]
        ],
        previous_state: OrbitalState | None,
    ) -> PassEvent:
        """Build one PassEvent from a visible sample group."""

        if not visible_samples:
            raise ValueError(
                "visible_samples must not be empty"
            )

        first_state, first_look = visible_samples[0]
        last_state, last_look = visible_samples[-1]

        aos = first_state.timestamp
        los = last_state.timestamp

        # If the visible interval contains only one sampled
        # point, estimate a minimal interval using the neighboring
        # sample when possible. This avoids creating a zero-duration
        # pass.
        if len(visible_samples) == 1:
            if previous_state is not None:
                delta = (
                    first_state.timestamp
                    - previous_state.timestamp
                ).total_seconds()

                if delta > 0:
                    aos = first_state.timestamp
                    los = (
                        first_state.timestamp
                        + timedelta(seconds=delta)
                    )
            else:
                los = (
                    first_state.timestamp
                    + timedelta(seconds=1.0)
                )

        max_elevation = max(
            look.elevation_deg
            for _, look in visible_samples
        )

        return PassEvent(
            satellite=first_state.satellite,
            aos=ensure_utc(aos),
            los=ensure_utc(los),
            max_elevation_deg=max_elevation,
            aos_azimuth_deg=first_look.azimuth_deg,
            los_azimuth_deg=last_look.azimuth_deg,
        )
