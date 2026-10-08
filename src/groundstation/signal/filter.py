"""
Digital signal filtering utilities.

The implementation intentionally uses standard-library Python
operations for the initial foundation. A future optimized backend
can use NumPy/SciPy without changing the public interface.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class FilterConfig:
    """Configuration for a moving-average low-pass filter."""

    window_size: int = 5

    def __post_init__(self) -> None:
        if self.window_size <= 0:
            raise ValueError("window_size must be greater than zero.")


class SignalFilter:
    """Basic digital signal filtering operations."""

    def __init__(self, config: FilterConfig | None = None) -> None:
        self.config = config or FilterConfig()

    def low_pass(
        self,
        samples: Iterable[complex],
    ) -> tuple[complex, ...]:
        """
        Apply a moving-average low-pass filter.

        This is a simple deterministic baseline implementation.
        Production SDR processing can later use FIR/IIR filters.
        """
        values = tuple(samples)

        if not values:
            return ()

        window = self.config.window_size
        result: list[complex] = []

        running_sum = 0j
        history: list[complex] = []

        for sample in values:
            if not isinstance(sample, complex):
                raise TypeError("Signal samples must be complex numbers.")

            history.append(sample)
            running_sum += sample

            if len(history) > window:
                running_sum -= history.pop(0)

            result.append(running_sum / len(history))

        return tuple(result)

    def high_pass(
        self,
        samples: Iterable[complex],
    ) -> tuple[complex, ...]:
        """
        Apply a simple high-pass operation.

        High-pass output is calculated as:

            original - low_pass(original)
        """
        values = tuple(samples)
        low_passed = self.low_pass(values)

        return tuple(
            original - filtered
            for original, filtered in zip(values, low_passed)
        )

    def remove_dc(
        self,
        samples: Iterable[complex],
    ) -> tuple[complex, ...]:
        """Remove the complex DC component from a signal."""
        values = tuple(samples)

        if not values:
            return ()

        mean = sum(values, 0j) / len(values)

        return tuple(sample - mean for sample in values)

    def smooth_magnitude(
        self,
        samples: Iterable[complex],
    ) -> tuple[float, ...]:
        """Calculate smoothed signal magnitude."""
        magnitudes = tuple(abs(sample) for sample in samples)

        if not magnitudes:
            return ()

        window = self.config.window_size
        result: list[float] = []
        history: list[float] = []

        running_sum = 0.0

        for magnitude in magnitudes:
            history.append(magnitude)
            running_sum += magnitude

            if len(history) > window:
                running_sum -= history.pop(0)

            result.append(running_sum / len(history))

        return tuple(result)


def normalize_signal(
    samples: Iterable[complex],
    peak: float = 1.0,
) -> tuple[complex, ...]:
    """
    Normalize complex samples to a requested peak amplitude.

    Args:
        samples: Complex signal samples.
        peak: Desired maximum magnitude.

    Returns:
        Normalized complex samples.

    Raises:
        ValueError: If peak is not positive.
    """
    if peak <= 0:
        raise ValueError("peak must be greater than zero.")

    values = tuple(samples)

    if not values:
        return ()

    maximum = max(abs(sample) for sample in values)

    if not math.isfinite(maximum):
        raise ValueError("Signal contains non-finite values.")

    if maximum == 0:
        return tuple(0j for _ in values)

    scale = peak / maximum

    return tuple(sample * scale for sample in values)
