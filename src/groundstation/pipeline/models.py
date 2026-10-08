"""
Data models for the OrbitWatch receive-processing pipeline.

The models in this module describe pipeline configuration, execution
statistics, and processing results without coupling the pipeline to
a specific SDR hardware implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DemodulationMode(str, Enum):
    """Supported demodulation modes."""

    FM = "FM"
    AFSK = "AFSK"
    GMSK = "GMSK"


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """
    Configuration for the SDR-to-DSP receive pipeline.

    The pipeline is deliberately configurable so the same processing
    engine can be used for different satellite signal types.
    """

    demodulation_mode: DemodulationMode = DemodulationMode.FM

    remove_dc: bool = True
    low_pass_enabled: bool = True
    normalize_enabled: bool = True

    filter_window_size: int = 5
    normalization_peak: float = 1.0

    samples_per_symbol: float = 1.0
    symbol_offset: int = 0

    afsk_mark_frequency_hz: float = 1200.0
    afsk_space_frequency_hz: float = 2200.0

    binary_threshold: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(
            self.demodulation_mode,
            DemodulationMode,
        ):
            try:
                object.__setattr__(
                    self,
                    "demodulation_mode",
                    DemodulationMode(self.demodulation_mode),
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "demodulation_mode must be FM, AFSK, or GMSK."
                ) from exc

        if self.filter_window_size <= 0:
            raise ValueError(
                "filter_window_size must be greater than zero."
            )

        if self.normalization_peak <= 0:
            raise ValueError(
                "normalization_peak must be greater than zero."
            )

        if self.samples_per_symbol <= 0:
            raise ValueError(
                "samples_per_symbol must be greater than zero."
            )

        if self.symbol_offset < 0:
            raise ValueError(
                "symbol_offset cannot be negative."
            )

        if self.afsk_mark_frequency_hz <= 0:
            raise ValueError(
                "afsk_mark_frequency_hz must be greater than zero."
            )

        if self.afsk_space_frequency_hz <= 0:
            raise ValueError(
                "afsk_space_frequency_hz must be greater than zero."
            )

        if (
            self.afsk_mark_frequency_hz
            == self.afsk_space_frequency_hz
        ):
            raise ValueError(
                "AFSK mark and space frequencies must differ."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible configuration dictionary."""

        return {
            "demodulation_mode": self.demodulation_mode.value,
            "remove_dc": self.remove_dc,
            "low_pass_enabled": self.low_pass_enabled,
            "normalize_enabled": self.normalize_enabled,
            "filter_window_size": self.filter_window_size,
            "normalization_peak": self.normalization_peak,
            "samples_per_symbol": self.samples_per_symbol,
            "symbol_offset": self.symbol_offset,
            "afsk_mark_frequency_hz": (
                self.afsk_mark_frequency_hz
            ),
            "afsk_space_frequency_hz": (
                self.afsk_space_frequency_hz
            ),
            "binary_threshold": self.binary_threshold,
        }


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Result produced by one receive-processing operation."""

    sample_rate_hz: float
    center_frequency_hz: float

    input_sample_count: int
    filtered_sample_count: int
    demodulated_sample_count: int
    synchronized_sample_count: int
    symbol_count: int

    demodulation_mode: DemodulationMode

    filtered_samples: tuple[complex, ...] = field(
        default_factory=tuple
    )
    demodulated_samples: tuple[float, ...] = field(
        default_factory=tuple
    )
    synchronized_samples: tuple[float, ...] = field(
        default_factory=tuple
    )
    binary_symbols: tuple[int, ...] = field(
        default_factory=tuple
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def duration_seconds(self) -> float:
        """Return the duration of the input sample block."""

        if self.sample_rate_hz <= 0:
            return 0.0

        return (
            self.input_sample_count
            / self.sample_rate_hz
        )

    @property
    def has_signal(self) -> bool:
        """Return whether the pipeline produced samples."""

        return (
            self.input_sample_count > 0
            and self.demodulated_sample_count > 0
        )

    @property
    def peak(self) -> float:
        """Return the peak magnitude of the demodulated signal."""

        if not self.demodulated_samples:
            return 0.0

        return max(
            abs(value)
            for value in self.demodulated_samples
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible result dictionary."""

        return {
            "sample_rate_hz": self.sample_rate_hz,
            "center_frequency_hz": (
                self.center_frequency_hz
            ),
            "input_sample_count": (
                self.input_sample_count
            ),
            "filtered_sample_count": (
                self.filtered_sample_count
            ),
            "demodulated_sample_count": (
                self.demodulated_sample_count
            ),
            "synchronized_sample_count": (
                self.synchronized_sample_count
            ),
            "symbol_count": self.symbol_count,
            "demodulation_mode": (
                self.demodulation_mode.value
            ),
            "duration_seconds": self.duration_seconds,
            "has_signal": self.has_signal,
            "peak": self.peak,
            "binary_symbols": list(
                self.binary_symbols
            ),
            "metadata": dict(self.metadata),
        }
