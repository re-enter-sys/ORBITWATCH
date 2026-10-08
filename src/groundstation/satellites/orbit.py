"""
Orbital geometry calculations for OrbitWatch.

Coordinates are Earth-centered Cartesian coordinates in kilometres.

This module provides the geometry layer. It does not attempt to
replace a precision SGP4/TLE propagator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


EARTH_RADIUS_KM = 6378.137


def ensure_utc(
    timestamp: datetime,
) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if not isinstance(
        timestamp,
        datetime,
    ):
        raise TypeError(
            "Timestamp must be a datetime."
        )

    if timestamp.tzinfo is None:
        raise ValueError(
            "Timestamp must be timezone-aware."
        )

    return timestamp.astimezone(
        timezone.utc
    )


def normalize_longitude(
    longitude_deg: float,
) -> float:
    """Normalize longitude into [-180, 180)."""

    if not math.isfinite(
        longitude_deg
    ):
        raise ValueError(
            "Longitude must be finite."
        )

    normalized = (
        longitude_deg + 180.0
    ) % 360.0 - 180.0

    if normalized == 180.0:
        return -180.0

    return normalized


@dataclass(frozen=True, slots=True)
class GroundStationLocation:
    """Ground-station geographic location."""

    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0
    name: str = "Ground Station"

    def __post_init__(self) -> None:
        for value, label in (
            (self.latitude_deg, "Latitude"),
            (self.longitude_deg, "Longitude"),
            (self.altitude_m, "Altitude"),
        ):
            if not math.isfinite(value):
                raise ValueError(
                    f"{label} must be finite."
                )

        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(
                "Latitude must be between -90 and 90 degrees."
            )

        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError(
                "Longitude must be between -180 and 180 degrees."
            )

        if self.altitude_m < -500.0:
            raise ValueError(
                "Ground-station altitude is unrealistically low."
            )


@dataclass(frozen=True, slots=True)
class OrbitalState:
    """Satellite Earth-centered Cartesian state."""

    satellite: str
    timestamp: datetime
    x_km: float
    y_km: float
    z_km: float

    velocity_x_km_s: float = 0.0
    velocity_y_km_s: float = 0.0
    velocity_z_km_s: float = 0.0

    def __post_init__(self) -> None:
        if not str(self.satellite).strip():
            raise ValueError(
                "Satellite name cannot be empty."
            )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )

        for value, label in (
            (self.x_km, "X position"),
            (self.y_km, "Y position"),
            (self.z_km, "Z position"),
            (
                self.velocity_x_km_s,
                "X velocity",
            ),
            (
                self.velocity_y_km_s,
                "Y velocity",
            ),
            (
                self.velocity_z_km_s,
                "Z velocity",
            ),
        ):
            if not math.isfinite(value):
                raise ValueError(
                    f"{label} must be finite."
                )

    @property
    def position_radius_km(self) -> float:
        """Distance from Earth's center."""

        return math.sqrt(
            self.x_km**2
            + self.y_km**2
            + self.z_km**2
        )

    @property
    def radius_km(self) -> float:
        """Alias for position_radius_km."""

        return self.position_radius_km

    @property
    def altitude_km(self) -> float:
        """Approximate altitude above Earth's mean radius."""

        return (
            self.position_radius_km
            - EARTH_RADIUS_KM
        )

    @property
    def velocity_km_s(self) -> float:
        """Velocity magnitude."""

        return math.sqrt(
            self.velocity_x_km_s**2
            + self.velocity_y_km_s**2
            + self.velocity_z_km_s**2
        )

    @property
    def vx_km_s(self) -> float:
        """Compatibility alias for X velocity."""

        return self.velocity_x_km_s

    @property
    def vy_km_s(self) -> float:
        """Compatibility alias for Y velocity."""

        return self.velocity_y_km_s

    @property
    def vz_km_s(self) -> float:
        """Compatibility alias for Z velocity."""

        return self.velocity_z_km_s


@dataclass(frozen=True, slots=True)
class LookAngles:
    """Ground-station look-angle solution."""

    elevation_deg: float
    azimuth_deg: float
    range_km: float

    def __post_init__(self) -> None:
        if not math.isfinite(
            self.elevation_deg
        ):
            raise ValueError(
                "Elevation must be finite."
            )

        if not math.isfinite(
            self.azimuth_deg
        ):
            raise ValueError(
                "Azimuth must be finite."
            )

        if not math.isfinite(
            self.range_km
        ):
            raise ValueError(
                "Range must be finite."
            )

        if self.range_km < 0:
            raise ValueError(
                "Range cannot be negative."
            )

    @property
    def visible(self) -> bool:
        """Return True when the satellite is above the horizon."""

        return self.elevation_deg >= 0.0


def _ground_station_ecef(
    station: GroundStationLocation,
) -> tuple[float, float, float]:
    """Convert ground-station coordinates to spherical-Earth ECEF."""

    latitude = math.radians(
        station.latitude_deg
    )

    longitude = math.radians(
        station.longitude_deg
    )

    radius_km = (
        EARTH_RADIUS_KM
        + station.altitude_m / 1000.0
    )

    x = (
        radius_km
        * math.cos(latitude)
        * math.cos(longitude)
    )

    y = (
        radius_km
        * math.cos(latitude)
        * math.sin(longitude)
    )

    z = (
        radius_km
        * math.sin(latitude)
    )

    return x, y, z


def calculate_look_angles(
    state: OrbitalState,
    station: GroundStationLocation,
) -> LookAngles:
    """Calculate elevation, azimuth and range."""

    if not isinstance(
        state,
        OrbitalState,
    ):
        raise TypeError(
            "state must be an OrbitalState."
        )

    if not isinstance(
        station,
        GroundStationLocation,
    ):
        raise TypeError(
            "station must be a GroundStationLocation."
        )

    station_x, station_y, station_z = (
        _ground_station_ecef(station)
    )

    dx = state.x_km - station_x
    dy = state.y_km - station_y
    dz = state.z_km - station_z

    range_km = math.sqrt(
        dx**2
        + dy**2
        + dz**2
    )

    if range_km <= 0.0:
        raise ValueError(
            "Satellite position cannot equal ground-station position."
        )

    latitude = math.radians(
        station.latitude_deg
    )

    longitude = math.radians(
        station.longitude_deg
    )

    east = (
        -math.sin(longitude) * dx
        + math.cos(longitude) * dy
    )

    north = (
        -math.sin(latitude)
        * math.cos(longitude)
        * dx
        - math.sin(latitude)
        * math.sin(longitude)
        * dy
        + math.cos(latitude) * dz
    )

    up = (
        math.cos(latitude)
        * math.cos(longitude)
        * dx
        + math.cos(latitude)
        * math.sin(longitude) * dy
        + math.sin(latitude) * dz
    )

    horizontal_range = math.hypot(
        east,
        north,
    )

    elevation_deg = math.degrees(
        math.atan2(
            up,
            horizontal_range,
        )
    )

    azimuth_deg = (
        math.degrees(
            math.atan2(
                east,
                north,
            )
        )
        % 360.0
    )

    return LookAngles(
        elevation_deg=elevation_deg,
        azimuth_deg=azimuth_deg,
        range_km=range_km,
    )


def calculate_subpoint(
    state: OrbitalState,
) -> tuple[float, float]:
    """Calculate approximate satellite latitude/longitude."""

    if not isinstance(
        state,
        OrbitalState,
    ):
        raise TypeError(
            "state must be an OrbitalState."
        )

    radius = state.position_radius_km

    if radius <= 0.0:
        raise ValueError(
            "Satellite radius must be positive."
        )

    latitude_deg = math.degrees(
        math.asin(
            max(
                -1.0,
                min(
                    1.0,
                    state.z_km / radius,
                ),
            )
        )
    )

    longitude_deg = math.degrees(
        math.atan2(
            state.y_km,
            state.x_km,
        )
    )

    return (
        latitude_deg,
        normalize_longitude(
            longitude_deg
        ),
    )
