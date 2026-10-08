"""
Tests for OrbitWatch orbital geometry.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from groundstation.satellites import (
    GroundStationLocation,
    OrbitalState,
    calculate_look_angles,
    calculate_subpoint,
    normalize_longitude,
)


def test_ground_station_location() -> None:
    station = GroundStationLocation(
        latitude_deg=17.0,
        longitude_deg=81.8,
        altitude_m=50.0,
        name="Test Station",
    )

    assert station.latitude_deg == 17.0
    assert station.longitude_deg == 81.8
    assert station.altitude_m == 50.0


def test_ground_station_invalid_latitude() -> None:
    with pytest.raises(ValueError):
        GroundStationLocation(
            latitude_deg=100.0,
            longitude_deg=0.0,
        )


def test_ground_station_invalid_longitude() -> None:
    with pytest.raises(ValueError):
        GroundStationLocation(
            latitude_deg=0.0,
            longitude_deg=200.0,
        )


def test_orbital_state_altitude() -> None:
    state = OrbitalState(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        x_km=7000.0,
        y_km=0.0,
        z_km=0.0,
    )

    assert state.position_radius_km == pytest.approx(
        7000.0
    )

    assert state.altitude_km == pytest.approx(
        7000.0 - 6378.137
    )


def test_orbital_velocity() -> None:
    state = OrbitalState(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        x_km=7000.0,
        y_km=0.0,
        z_km=0.0,
        velocity_x_km_s=1.0,
        velocity_y_km_s=2.0,
        velocity_z_km_s=2.0,
    )

    assert state.velocity_km_s == pytest.approx(3.0)


def test_subpoint_equator_prime_meridian() -> None:
    state = OrbitalState(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        x_km=7000.0,
        y_km=0.0,
        z_km=0.0,
    )

    latitude, longitude = calculate_subpoint(state)

    assert latitude == pytest.approx(0.0)
    assert longitude == pytest.approx(0.0)


def test_subpoint_north_pole() -> None:
    state = OrbitalState(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        x_km=0.0,
        y_km=0.0,
        z_km=7000.0,
    )

    latitude, longitude = calculate_subpoint(state)

    assert latitude == pytest.approx(90.0)
    assert longitude == pytest.approx(0.0)


def test_satellite_overhead() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    state = OrbitalState(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        x_km=7000.0,
        y_km=0.0,
        z_km=0.0,
    )

    angles = calculate_look_angles(
        state,
        station,
    )

    assert angles.elevation_deg == pytest.approx(
        90.0,
        abs=0.01,
    )

    assert angles.range_km == pytest.approx(
        7000.0 - 6378.137,
        abs=0.01,
    )

    assert angles.visible


def test_satellite_below_horizon() -> None:
    station = GroundStationLocation(
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    state = OrbitalState(
        satellite="TESTSAT",
        timestamp=datetime.now(timezone.utc),
        x_km=-7000.0,
        y_km=0.0,
        z_km=0.0,
    )

    angles = calculate_look_angles(
        state,
        station,
    )

    assert angles.elevation_deg < 0.0
    assert not angles.visible


def test_normalize_longitude() -> None:
    assert normalize_longitude(0.0) == pytest.approx(0.0)
    assert normalize_longitude(180.0) == pytest.approx(-180.0)
    assert normalize_longitude(360.0) == pytest.approx(0.0)
    assert normalize_longitude(-181.0) == pytest.approx(179.0)
