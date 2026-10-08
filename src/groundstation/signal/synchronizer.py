"""
Symbol synchronization primitives.

Synchronization aligns a sampled signal with the expected symbol
timing before binary or packet-level decoding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SynchronizationResult:
    """Result of symbol synchronization."""

    samples: tuple[float, ...]
    samples_per_symbol: float
    offset: int

    @property
    def symbol_count(self) -> int:
        """Return the number of complete symbols represented."""
        if self.samples_per_symbol <= 0:
            return 0

        return int(
            len(self.samples) / self.samples_per_symbol
        )


class SymbolSynchronizer:
    """
    Simple deterministic symbol synchronizer.

    This baseline implementation selects a sampling offset and
    extracts one sample per symbol.

    More advanced timing recovery algorithms can replace this
    implementation without changing the public result structure.
    """

    def __init__(self, samples_per_symbol: float) -> None:
        if samples_per_symbol <= 0:
            raise ValueError(
                "samples_per_symbol must be greater than zero."
            )

        self.samples_per_symbol = samples_per_symbol

    def synchronize(
        self,
        samples: Iterable[float],
        offset: int = 0,
    ) -> SynchronizationResult:
        """
        Extract symbol-spaced samples.

        Args:
            samples: Real-valued demodulated samples.
            offset: Initial sample offset.

        Returns:
            SynchronizationResult.
        """
        values = tuple(samples)

        if offset < 0:
            raise ValueError("offset cannot be negative.")

        if offset >= len(values) and values:
            raise ValueError(
                "offset must be smaller than the sample count."
            )

        if not values:
            return SynchronizationResult(
                samples=(),
                samples_per_symbol=self.samples_per_symbol,
                offset=offset,
            )

        step = self.samples_per_symbol

        result: list[float] = []

        position = float(offset)

        while position < len(values):
            index = int(round(position))

            if index >= len(values):
                break

            result.append(values[index])
            position += step

        return SynchronizationResult(
            samples=tuple(result),
            samples_per_symbol=self.samples_per_symbol,
            offset=offset,
        )

    def recover_binary(
        self,
        samples: Iterable[float],
        threshold: float = 0.0,
        offset: int = 0,
    ) -> tuple[int, ...]:
        """
        Synchronize a signal and convert symbols into binary values.

        Values >= threshold become 1.
        Values < threshold become 0.
        """
        synchronized = self.synchronize(
            samples,
            offset=offset,
        )

        return tuple(
            1 if sample >= threshold else 0
            for sample in synchronized.samples
        )
