"""
IQ sample representation and validation.

IQ data is the fundamental digital representation used by many
software-defined radio systems. OrbitWatch represents each sample
as a complex value:

    I + jQ

where I is the in-phase component and Q is the quadrature component.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable, Iterator


class IQSampleFormat(str, Enum):
    """Supported logical IQ sample representations."""

    COMPLEX64 = "complex64"
    COMPLEX128 = "complex128"


@dataclass(frozen=True)
class IQSampleBuffer:
    """
    Immutable container for a sequence of complex IQ samples.
    """

    samples: tuple[complex, ...]
    sample_rate_hz: float
    center_frequency_hz: float
    format: IQSampleFormat = IQSampleFormat.COMPLEX64

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than zero.")

        if not math.isfinite(self.sample_rate_hz):
            raise ValueError("sample_rate_hz must be finite.")

        if not math.isfinite(self.center_frequency_hz):
            raise ValueError("center_frequency_hz must be finite.")

        for sample in self.samples:
            if not isinstance(sample, complex):
                raise TypeError("All IQ samples must be complex numbers.")

            if not (
                math.isfinite(sample.real)
                and math.isfinite(sample.imag)
            ):
                raise ValueError("IQ samples must contain finite values.")

    @classmethod
    def from_iterable(
        cls,
        samples: Iterable[complex],
        sample_rate_hz: float,
        center_frequency_hz: float,
        sample_format: IQSampleFormat = IQSampleFormat.COMPLEX64,
    ) -> "IQSampleBuffer":
        """Create an IQ buffer from any iterable of complex samples."""
        return cls(
            samples=tuple(samples),
            sample_rate_hz=sample_rate_hz,
            center_frequency_hz=center_frequency_hz,
            format=sample_format,
        )

    @property
    def count(self) -> int:
        """Return the number of samples."""
        return len(self.samples)

    @property
    def duration_seconds(self) -> float:
        """Return the duration represented by the buffer."""
        return self.count / self.sample_rate_hz

    @property
    def mean_power(self) -> float:
        """Return average signal power."""
        if not self.samples:
            return 0.0

        return sum(
            sample.real**2 + sample.imag**2
            for sample in self.samples
        ) / self.count

    @property
    def rms_amplitude(self) -> float:
        """Return root-mean-square signal amplitude."""
        return math.sqrt(self.mean_power)

    def peak_amplitude(self) -> float:
        """Return the largest absolute sample magnitude."""
        if not self.samples:
            return 0.0

        return max(abs(sample) for sample in self.samples)

    def __len__(self) -> int:
        return self.count

    def __iter__(self) -> Iterator[complex]:
        return iter(self.samples)

    def __getitem__(self, index: int) -> complex:
        return self.samples[index]


def interleaved_iq_to_complex(
    values: Iterable[float],
) -> tuple[complex, ...]:
    """
    Convert interleaved I/Q values into complex samples.

    Input:

        I0, Q0, I1, Q1, ...

    Output:

        I0+jQ0, I1+jQ1, ...

    Raises:
        ValueError: If the number of values is odd.
    """
    values_tuple = tuple(values)

    if len(values_tuple) % 2 != 0:
        raise ValueError(
            "Interleaved IQ data must contain an even number of values."
        )

    return tuple(
        complex(values_tuple[index], values_tuple[index + 1])
        for index in range(0, len(values_tuple), 2)
    )


def complex_to_interleaved_iq(
    samples: Iterable[complex],
) -> tuple[float, ...]:
    """Convert complex samples into interleaved I/Q values."""
    result: list[float] = []

    for sample in samples:
        if not isinstance(sample, complex):
            raise TypeError("All samples must be complex numbers.")

        result.extend((sample.real, sample.imag))

    return tuple(result)
