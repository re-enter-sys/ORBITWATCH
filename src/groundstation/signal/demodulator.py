"""
Digital signal demodulators.

The implementations here provide deterministic baseline
demodulators suitable for testing and recorded-sample processing.

The architecture is intentionally separated from the SDR device so
that real satellite signals can later use optimized DSP backends.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class DemodulatedSignal:
    """Result produced by a demodulator."""

    samples: tuple[float, ...]
    sample_rate_hz: float
    mode: str

    @property
    def count(self) -> int:
        """Return the number of demodulated samples."""
        return len(self.samples)

    @property
    def duration_seconds(self) -> float:
        """Return the signal duration."""
        if self.sample_rate_hz <= 0:
            return 0.0

        return self.count / self.sample_rate_hz

    @property
    def peak(self) -> float:
        """Return the largest absolute sample value."""
        if not self.samples:
            return 0.0

        return max(abs(value) for value in self.samples)


class FMDemodulator:
    """
    Phase-difference FM demodulator.

    For complex baseband samples:

        phase_difference =
            angle(current * conjugate(previous))

    The phase difference is proportional to instantaneous frequency.
    """

    mode = "FM"

    def demodulate(
        self,
        samples: Iterable[complex],
        sample_rate_hz: float,
    ) -> DemodulatedSignal:
        """Demodulate complex IQ samples using phase differences."""
        if sample_rate_hz <= 0:
            raise ValueError(
                "sample_rate_hz must be greater than zero."
            )

        values = tuple(samples)

        if not values:
            return DemodulatedSignal(
                samples=(),
                sample_rate_hz=sample_rate_hz,
                mode=self.mode,
            )

        result: list[float] = [0.0]

        previous = values[0]

        for current in values[1:]:
            if not isinstance(current, complex):
                raise TypeError(
                    "FM demodulation requires complex samples."
                )

            product = current * previous.conjugate()
            phase = math.atan2(product.imag, product.real)

            result.append(phase)

            previous = current

        return DemodulatedSignal(
            samples=tuple(result),
            sample_rate_hz=sample_rate_hz,
            mode=self.mode,
        )


class AFSKDemodulator:
    """
    Basic AFSK discriminator.

    This stage converts phase changes into a real-valued stream.
    Frequency/bit decisions are deliberately left to the protocol
    and symbol-processing layers.
    """

    mode = "AFSK"

    def __init__(
        self,
        mark_frequency_hz: float = 1200.0,
        space_frequency_hz: float = 2200.0,
    ) -> None:
        if mark_frequency_hz <= 0:
            raise ValueError(
                "mark_frequency_hz must be greater than zero."
            )

        if space_frequency_hz <= 0:
            raise ValueError(
                "space_frequency_hz must be greater than zero."
            )

        if mark_frequency_hz == space_frequency_hz:
            raise ValueError(
                "mark and space frequencies must differ."
            )

        self.mark_frequency_hz = mark_frequency_hz
        self.space_frequency_hz = space_frequency_hz

        self._fm = FMDemodulator()

    def demodulate(
        self,
        samples: Iterable[complex],
        sample_rate_hz: float,
    ) -> DemodulatedSignal:
        """
        Produce a discriminator output suitable for AFSK processing.
        """
        result = self._fm.demodulate(
            samples,
            sample_rate_hz,
        )

        return DemodulatedSignal(
            samples=result.samples,
            sample_rate_hz=result.sample_rate_hz,
            mode=self.mode,
        )


class GMSKDemodulator:
    """
    GMSK demodulation foundation.

    GMSK uses continuous phase modulation. The first processing
    stage is a phase discriminator; Gaussian filtering and symbol
    recovery are handled by subsequent processing stages.
    """

    mode = "GMSK"

    def demodulate(
        self,
        samples: Iterable[complex],
        sample_rate_hz: float,
    ) -> DemodulatedSignal:
        """Demodulate complex samples using phase differences."""
        fm_result = FMDemodulator().demodulate(
            samples,
            sample_rate_hz,
        )

        return DemodulatedSignal(
            samples=fm_result.samples,
            sample_rate_hz=fm_result.sample_rate_hz,
            mode=self.mode,
        )
