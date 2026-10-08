"""
Tests for OrbitWatch satellite pass prediction.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from groundstation.satellites import (
    GroundStationLocation,
    OrbitalState,
    PassPredictor,
    PassStatus,
)


def make_state(
    timestamp: datetime,
    x: float,
    y: float,
    z: float = 0.0,
) -> OrbitalState:
    return OrbitalState(
        satellite="TESTSAT",
        timestamp=timestamp,
        x_km=x,
        y_km=y,
        z_km=z,
    )


def test_no_states_returns_no_passes() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    predictor = PassPredictor(station)

    assert predictor.predict([]) == []


def test_overhead_pass_is_detected() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    predictor = PassPredictor(
        station,
        minimum_elevation_deg=10.0,
    )

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    states = [
        make_state(
            start,
            -7000.0,
            0.0,
        ),
        make_state(
            start + timedelta(minutes=1),
            -6500.0,
            0.0,
        ),
        make_state(
            start + timedelta(minutes=2),
            7000.0,
            0.0,
        ),
    ]

    passes = predictor.predict(states)

    assert len(passes) == 1

    event = passes[0]

    assert event.satellite == "TESTSAT"
    assert event.max_elevation_deg >= 10.0
    assert event.aos < event.los


def test_pass_event_serialization() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    predictor = PassPredictor(
        station,
        minimum_elevation_deg=0.0,
    )

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    states = [
        make_state(
            start,
            7000.0,
            0.0,
        )
    ]

    passes = predictor.predict(states)

    assert len(passes) == 1

    data = passes[0].to_dict()

    assert data["satellite"] == "TESTSAT"
    assert "aos" in data
    assert "los" in data
    assert "max_elevation_deg" in data
    assert "status" in data


def test_provider_prediction() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    predictor = PassPredictor(station)

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    def provider(
        timestamp: datetime,
    ) -> OrbitalState:
        return make_state(
            timestamp,
            7000.0,
            0.0,
        )

    passes = predictor.predict_from_provider(
        provider,
        start,
        duration_seconds=60.0,
        step_seconds=10.0,
    )

    assert len(passes) == 1
    assert passes[0].satellite == "TESTSAT"


def test_invalid_prediction_parameters() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    predictor = PassPredictor(station)

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    def provider(
        timestamp: datetime,
    ) -> OrbitalState:
        return make_state(
            timestamp,
            7000.0,
            0.0,
        )

    with pytest.raises(ValueError):
        predictor.predict_from_provider(
            provider,
            start,
            duration_seconds=0,
            step_seconds=10,
        )

    with pytest.raises(ValueError):
        predictor.predict_from_provider(
            provider,
            start,
            duration_seconds=60,
            step_seconds=0,
        )


def test_pass_status_is_valid() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    predictor = PassPredictor(station)

    start = datetime.now(timezone.utc)

    states = [
        make_state(
            start,
            7000.0,
            0.0,
        )
    ]

    passes = predictor.predict(states)

    assert len(passes) == 1
    assert passes[0].status in {
        PassStatus.UPCOMING,
        PassStatus.ACTIVE,
        PassStatus.COMPLETED,
    }
