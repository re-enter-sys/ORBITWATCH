"""
OrbitWatch satellite catalog, orbital geometry and pass prediction.
"""

from .catalog import Satellite, SatelliteCatalog
from .orbit import (
    EARTH_RADIUS_KM,
    GroundStationLocation,
    LookAngles,
    OrbitalState,
    calculate_look_angles,
    calculate_subpoint,
    ensure_utc,
    normalize_longitude,
)
from .pass_predictor import (
    PassEvent,
    PassPredictor,
    PassStatus,
)

__all__ = [
    "EARTH_RADIUS_KM",
    "GroundStationLocation",
    "LookAngles",
    "OrbitalState",
    "PassEvent",
    "PassPredictor",
    "PassStatus",
    "Satellite",
    "SatelliteCatalog",
    "calculate_look_angles",
    "calculate_subpoint",
    "ensure_utc",
    "normalize_longitude",
]
