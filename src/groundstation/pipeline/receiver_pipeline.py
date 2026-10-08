"""
OrbitWatch receiver processing pipeline.

Pipeline:

    IQ samples
        ↓
    DC removal
        ↓
    Low-pass filtering
        ↓
    Normalization
        ↓
    Demodulation
        ↓
    Symbol synchronization
        ↓
    Binary recovery
        ↓
    PipelineResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Any

from groundstation.sdr.iq import IQSampleBuffer
from groundstation.sdr.receiver import SDRReceiver
from groundstation.signal.demodulator import (
    AFSKDemodulator,
    FMDemodulator,
    GMSKDemodulator,
)
from groundstation.signal.filter import (
    FilterConfig,
    SignalFilter,
    normalize_signal,
)
from groundstation.signal.synchronizer import SymbolSynchronizer


class DemodulationMode(str, Enum):
    """Supported demodulation modes."""

    FM = "FM"
    AFSK = "AFSK"
    GMSK = "GMSK"


class PipelineState(str, Enum):
    """Runtime state of the receiver pipeline."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for the SDR processing pipeline."""

    demodulation_mode: DemodulationMode = (
        DemodulationMode.FM
    )

    remove_dc: bool = True
    low_pass_enabled: bool = True
    normalize_enabled: bool = True

    filter_window_size: int = 5
    normalization_peak: float = 1.0

    samples_per_symbol: float = 1.0
    symbol_offset: int = 0

    afsk_mark_frequency_hz: float = 1200.0
    afsk_space_frequency_hz: float = 2200.0

    def __post_init__(self) -> None:
        """Validate pipeline configuration."""

        mode = self.demodulation_mode

        if isinstance(mode, str):
            try:
                mode = DemodulationMode(mode.upper())
            except ValueError as exc:
                raise ValueError(
                    "demodulation_mode must be FM, AFSK, or GMSK."
                ) from exc

            object.__setattr__(
                self,
                "demodulation_mode",
                mode,
            )

        elif not isinstance(mode, DemodulationMode):
            raise ValueError(
                "demodulation_mode must be a DemodulationMode "
                "or a supported string."
            )

        if self.filter_window_size <= 0:
            raise ValueError(
                "filter_window_size must be greater than zero."
            )

        if not math.isfinite(self.normalization_peak):
            raise ValueError(
                "normalization_peak must be finite."
            )

        if self.normalization_peak <= 0:
            raise ValueError(
                "normalization_peak must be greater than zero."
            )

        if not math.isfinite(self.samples_per_symbol):
            raise ValueError(
                "samples_per_symbol must be finite."
            )

        if self.samples_per_symbol <= 0:
            raise ValueError(
                "samples_per_symbol must be greater than zero."
            )

        if self.symbol_offset < 0:
            raise ValueError(
                "symbol_offset cannot be negative."
            )

        if not math.isfinite(
            self.afsk_mark_frequency_hz
        ):
            raise ValueError(
                "afsk_mark_frequency_hz must be finite."
            )

        if not math.isfinite(
            self.afsk_space_frequency_hz
        ):
            raise ValueError(
                "afsk_space_frequency_hz must be finite."
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
        """Return a JSON-compatible configuration mapping."""

        return {
            "demodulation_mode": (
                self.demodulation_mode.value
            ),
            "remove_dc": self.remove_dc,
            "low_pass_enabled": self.low_pass_enabled,
            "normalize_enabled": self.normalize_enabled,
            "filter_window_size": self.filter_window_size,
            "normalization_peak": (
                self.normalization_peak
            ),
            "samples_per_symbol": (
                self.samples_per_symbol
            ),
            "symbol_offset": self.symbol_offset,
            "afsk_mark_frequency_hz": (
                self.afsk_mark_frequency_hz
            ),
            "afsk_space_frequency_hz": (
                self.afsk_space_frequency_hz
            ),
        }


@dataclass(frozen=True)
class PipelineStatus:
    """Current runtime status of the pipeline."""

    state: PipelineState
    running: bool
    processed_blocks: int
    processed_samples: int
    last_result_available: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize status."""

        return {
            "state": self.state.value,
            "running": self.running,
            "processed_blocks": self.processed_blocks,
            "processed_samples": self.processed_samples,
            "last_result_available": (
                self.last_result_available
            ),
        }


@dataclass(frozen=True)
class PipelineResult:
    """Result produced by one pipeline processing operation."""

    input_samples: tuple[complex, ...]
    filtered_samples: tuple[complex, ...]
    demodulated_samples: tuple[float, ...]
    synchronized_samples: tuple[float, ...]
    binary_symbols: tuple[int, ...]

    sample_rate_hz: float
    center_frequency_hz: float

    demodulation_mode: DemodulationMode

    processing_time_seconds: float = 0.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def input_sample_count(self) -> int:
        """Number of input IQ samples."""

        return len(self.input_samples)

    @property
    def filtered_sample_count(self) -> int:
        """Number of filtered samples."""

        return len(self.filtered_samples)

    @property
    def demodulated_sample_count(self) -> int:
        """Number of demodulated samples."""

        return len(self.demodulated_samples)

    @property
    def synchronized_sample_count(self) -> int:
        """Number of synchronized samples."""

        return len(self.synchronized_samples)

    @property
    def symbol_count(self) -> int:
        """Number of recovered binary symbols."""

        return len(self.binary_symbols)

    @property
    def duration_seconds(self) -> float:
        """Duration represented by the input IQ block."""

        if self.sample_rate_hz <= 0:
            return 0.0

        return (
            self.input_sample_count
            / self.sample_rate_hz
        )

    @property
    def peak(self) -> float:
        """Peak absolute amplitude of demodulated samples."""

        if not self.demodulated_samples:
            return 0.0

        return max(
            abs(value)
            for value in self.demodulated_samples
        )

    @property
    def has_signal(self) -> bool:
        """
        Return True when the input contains a valid signal block.

        A valid non-empty IQ block is considered signal-bearing even
        when the demodulator produces zero-valued samples.
        """

        if not self.input_samples:
            return False

        return all(
            math.isfinite(sample.real)
            and math.isfinite(sample.imag)
            for sample in self.input_samples
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result into JSON-compatible data."""

        return {
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
            "sample_rate_hz": self.sample_rate_hz,
            "center_frequency_hz": (
                self.center_frequency_hz
            ),
            "demodulation_mode": (
                self.demodulation_mode.value
            ),
            "duration_seconds": (
                self.duration_seconds
            ),
            "peak": self.peak,
            "has_signal": self.has_signal,
            "processing_time_seconds": (
                self.processing_time_seconds
            ),
            "input_samples": [
                {
                    "real": sample.real,
                    "imag": sample.imag,
                }
                for sample in self.input_samples
            ],
            "filtered_samples": [
                {
                    "real": sample.real,
                    "imag": sample.imag,
                }
                for sample in self.filtered_samples
            ],
            "demodulated_samples": list(
                self.demodulated_samples
            ),
            "synchronized_samples": list(
                self.synchronized_samples
            ),
            "binary_symbols": list(
                self.binary_symbols
            ),
            "metadata": dict(self.metadata),
        }


class ReceiverPipeline:
    """Connect the SDR receiver to signal processing."""

    def __init__(
        self,
        receiver: SDRReceiver,
        config: PipelineConfig | None = None,
    ) -> None:
        if not isinstance(receiver, SDRReceiver):
            raise TypeError(
                "receiver must be an SDRReceiver."
            )

        self.receiver = receiver
        self.config = config or PipelineConfig()

        self._state = PipelineState.IDLE
        self._processed_blocks = 0
        self._processed_samples = 0
        self._last_result: PipelineResult | None = None

    @property
    def state(self) -> PipelineState:
        """Return current pipeline state."""

        return self._state

    @property
    def is_running(self) -> bool:
        """Return whether the pipeline is running."""

        return self._state == PipelineState.RUNNING

    @property
    def last_result(self) -> PipelineResult | None:
        """Return the most recent result."""

        return self._last_result

    def start(self) -> None:
        """Start the underlying SDR receiver."""

        self.receiver.start()
        self._state = PipelineState.RUNNING

    def stop(self) -> None:
        """Stop the underlying SDR receiver."""

        self.receiver.stop()
        self._state = PipelineState.STOPPED

    def reset_statistics(self) -> None:
        """Reset cumulative processing statistics."""

        self._processed_blocks = 0
        self._processed_samples = 0
        self._last_result = None

        if self._state == PipelineState.ERROR:
            self._state = PipelineState.IDLE

    def status(self) -> PipelineStatus:
        """Return current pipeline status."""

        return PipelineStatus(
            state=self._state,
            running=self.is_running,
            processed_blocks=(
                self._processed_blocks
            ),
            processed_samples=(
                self._processed_samples
            ),
            last_result_available=(
                self._last_result is not None
            ),
        )

    def _create_demodulator(self):
        """Create the configured demodulator."""

        mode = self.config.demodulation_mode

        if mode == DemodulationMode.FM:
            return FMDemodulator()

        if mode == DemodulationMode.AFSK:
            return AFSKDemodulator(
                mark_frequency_hz=(
                    self.config.afsk_mark_frequency_hz
                ),
                space_frequency_hz=(
                    self.config.afsk_space_frequency_hz
                ),
            )

        if mode == DemodulationMode.GMSK:
            return GMSKDemodulator()

        raise ValueError(
            f"Unsupported demodulation mode: {mode}"
        )

    def process(
        self,
        iq_buffer: IQSampleBuffer,
    ) -> PipelineResult:
        """Process an existing IQ sample buffer."""

        if not isinstance(iq_buffer, IQSampleBuffer):
            raise TypeError(
                "iq_buffer must be an IQSampleBuffer."
            )

        started = time.perf_counter()

        try:
            input_samples = tuple(
                iq_buffer.samples
            )

            # ----------------------------------------------------------
            # Stage 1: DC removal
            # ----------------------------------------------------------

            stage = input_samples

            signal_filter = SignalFilter(
                config=FilterConfig(
                    window_size=(
                        self.config.filter_window_size
                    )
                )
            )

            if self.config.remove_dc:
                stage = signal_filter.remove_dc(
                    stage
                )

            # ----------------------------------------------------------
            # Stage 2: low-pass filtering
            # ----------------------------------------------------------

            if self.config.low_pass_enabled:
                filtered = signal_filter.low_pass(
                    stage
                )
            else:
                filtered = tuple(stage)

            # ----------------------------------------------------------
            # Stage 3: normalization
            # ----------------------------------------------------------

            if self.config.normalize_enabled:
                filtered = normalize_signal(
                    filtered,
                    peak=(
                        self.config.normalization_peak
                    ),
                )

            # ----------------------------------------------------------
            # Stage 4: demodulation
            # ----------------------------------------------------------

            demodulator = self._create_demodulator()

            demodulated_result = (
                demodulator.demodulate(
                    filtered,
                    iq_buffer.sample_rate_hz,
                )
            )

            demodulated = tuple(
                demodulated_result.samples
            )

            # ----------------------------------------------------------
            # Stage 5: symbol synchronization
            # ----------------------------------------------------------

            synchronizer = SymbolSynchronizer(
                samples_per_symbol=(
                    self.config.samples_per_symbol
                )
            )

            synchronized_result = (
                synchronizer.synchronize(
                    demodulated,
                    offset=self.config.symbol_offset,
                )
            )

            synchronized = tuple(
                synchronized_result.samples
            )

            # ----------------------------------------------------------
            # Stage 6: binary recovery
            #
            # IMPORTANT:
            # The existing SymbolSynchronizer already defines
            # threshold=0.0 as its default. The pipeline configuration
            # does not need its own threshold field.
            # ----------------------------------------------------------

            binary_symbols = (
                synchronizer.recover_binary(
                    demodulated,
                    offset=self.config.symbol_offset,
                )
            )

            processing_time = (
                time.perf_counter() - started
            )

            metadata = {
                "source": "iq_buffer",
                "demodulator_mode": (
                    self.config.demodulation_mode.value
                ),
                "sample_format": (
                    iq_buffer.format.value
                ),
                "sample_rate_hz": (
                    iq_buffer.sample_rate_hz
                ),
                "center_frequency_hz": (
                    iq_buffer.center_frequency_hz
                ),
                "input_sample_count": (
                    len(input_samples)
                ),
                "filtered_sample_count": (
                    len(filtered)
                ),
                "demodulated_sample_count": (
                    len(demodulated)
                ),
                "synchronized_sample_count": (
                    len(synchronized)
                ),
                "symbol_count": (
                    len(binary_symbols)
                ),
            }

            result = PipelineResult(
                input_samples=input_samples,
                filtered_samples=tuple(
                    filtered
                ),
                demodulated_samples=(
                    demodulated
                ),
                synchronized_samples=(
                    synchronized
                ),
                binary_symbols=tuple(
                    int(symbol)
                    for symbol in binary_symbols
                ),
                sample_rate_hz=(
                    iq_buffer.sample_rate_hz
                ),
                center_frequency_hz=(
                    iq_buffer.center_frequency_hz
                ),
                demodulation_mode=(
                    self.config.demodulation_mode
                ),
                processing_time_seconds=(
                    processing_time
                ),
                metadata=metadata,
            )

            self._processed_blocks += 1
            self._processed_samples += (
                len(input_samples)
            )
            self._last_result = result

            if self._state == PipelineState.ERROR:
                self._state = PipelineState.RUNNING

            return result

        except Exception:
            self._state = PipelineState.ERROR
            raise

    def capture_and_process(
        self,
        sample_count: int,
    ) -> PipelineResult:
        """Capture IQ samples from the SDR and process them."""

        if sample_count <= 0:
            raise ValueError(
                "sample_count must be greater than zero."
            )

        if not self.receiver.is_receiving:
            raise RuntimeError(
                "Receiver must be running before capture."
            )

        iq_buffer = self.receiver.capture(
            sample_count
        )

        return self.process(iq_buffer)

    def statistics(self) -> dict[str, Any]:
        """Return cumulative pipeline statistics."""

        last_result = self._last_result

        return {
            "state": self._state.value,
            "running": self.is_running,
            "processed_blocks": (
                self._processed_blocks
            ),
            "processed_samples": (
                self._processed_samples
            ),
            "last_result_available": (
                last_result is not None
            ),
            "last_input_sample_count": (
                last_result.input_sample_count
                if last_result is not None
                else 0
            ),
            "last_demodulated_sample_count": (
                last_result.demodulated_sample_count
                if last_result is not None
                else 0
            ),
            "last_symbol_count": (
                last_result.symbol_count
                if last_result is not None
                else 0
            ),
        }

    def stats(self) -> dict[str, Any]:
        """Backward-compatible alias for statistics()."""

        return self.statistics()
