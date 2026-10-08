"""
Signal-processing subsystem for OrbitWatch.

Provides filtering, demodulation, normalization, and symbol
synchronization primitives for received satellite signals.
"""

from .demodulator import (
    AFSKDemodulator,
    DemodulatedSignal,
    FMDemodulator,
    GMSKDemodulator,
)
from .filter import (
    FilterConfig,
    SignalFilter,
    normalize_signal,
)
from .synchronizer import (
    SynchronizationResult,
    SymbolSynchronizer,
)

__all__ = [
    "AFSKDemodulator",
    "DemodulatedSignal",
    "FMDemodulator",
    "GMSKDemodulator",
    "FilterConfig",
    "SignalFilter",
    "normalize_signal",
    "SynchronizationResult",
    "SymbolSynchronizer",
]
