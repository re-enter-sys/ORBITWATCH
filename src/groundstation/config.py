"""
Central configuration for the OrbitWatch ground station.

The configuration is intentionally lightweight at this stage.
Hardware-specific and protocol-specific settings will be added
as their respective subsystems are implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SATELLITE_DATA_DIR = DATA_DIR / "satellites"
SAMPLE_DATA_DIR = DATA_DIR / "samples"
TELEMETRY_DATA_DIR = DATA_DIR / "telemetry"
RECORDING_DATA_DIR = DATA_DIR / "recordings"


@dataclass(frozen=True)
class SDRConfig:
    """Configuration for the software-defined radio."""

    device_index: int = 0
    center_frequency_hz: float = 145_800_000.0
    sample_rate_hz: float = 2_048_000.0
    gain: str = "auto"
    ppm_correction: int = 0


@dataclass(frozen=True)
class GroundStationConfig:
    """Application-wide ground station configuration."""

    name: str = "OrbitWatch"
    version: str = "0.1.0"
    timezone: str = "UTC"
    log_level: str = "INFO"

    data_dir: Path = DATA_DIR
    satellite_data_dir: Path = SATELLITE_DATA_DIR
    sample_data_dir: Path = SAMPLE_DATA_DIR
    telemetry_data_dir: Path = TELEMETRY_DATA_DIR
    recording_data_dir: Path = RECORDING_DATA_DIR

    sdr: SDRConfig = field(default_factory=SDRConfig)

    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 5000


def get_default_config() -> GroundStationConfig:
    """
    Return the default OrbitWatch configuration.

    Returns:
        GroundStationConfig: Default application configuration.
    """
    return GroundStationConfig()


def ensure_data_directories(
    config: GroundStationConfig | None = None,
) -> None:
    """
    Create the data directories required by OrbitWatch.

    Args:
        config: Optional custom configuration. If omitted, the
            default configuration is used.
    """
    active_config = config or get_default_config()

    directories = (
        active_config.data_dir,
        active_config.satellite_data_dir,
        active_config.sample_data_dir,
        active_config.telemetry_data_dir,
        active_config.recording_data_dir,
    )

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
