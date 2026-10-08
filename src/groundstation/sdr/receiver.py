"""
SDR receiver abstraction.

The receiver controls configuration and acquisition state while
keeping the actual hardware backend isolated. This allows OrbitWatch
to support real SDR hardware and replay/sample sources through the
same higher-level interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import time
from typing import Callable, Iterable

from .device import SDRDevice, SDRDeviceManager, normalize_device_index
from .iq import IQSampleBuffer, IQSampleFormat


LOGGER = logging.getLogger(__name__)


class ReceiverState(str, Enum):
    """Receiver lifecycle states."""

    IDLE = "idle"
    READY = "ready"
    RECEIVING = "receiving"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True)
class ReceiverConfig:
    """Runtime configuration for an SDR receiver."""

    center_frequency_hz: float = 145_800_000.0
    sample_rate_hz: float = 2_048_000.0
    gain: str = "auto"
    ppm_correction: int = 0
    device_index: int = 0

    def validate(self) -> None:
        """Validate receiver parameters."""
        if self.center_frequency_hz <= 0:
            raise ValueError(
                "center_frequency_hz must be greater than zero."
            )

        if self.sample_rate_hz <= 0:
            raise ValueError(
                "sample_rate_hz must be greater than zero."
            )

        if not isinstance(self.ppm_correction, int):
            raise TypeError("ppm_correction must be an integer.")

        if self.device_index < 0:
            raise ValueError("device_index cannot be negative.")


SampleProvider = Callable[[int], Iterable[complex]]


class SDRReceiver:
    """
    High-level SDR receiver.

    Hardware acquisition is intentionally injectable through
    ``sample_provider``. The default receiver therefore remains
    usable for software development without physical SDR hardware.
    """

    def __init__(
        self,
        config: ReceiverConfig | None = None,
        device_manager: SDRDeviceManager | None = None,
        sample_provider: SampleProvider | None = None,
    ) -> None:
        self.config = config or ReceiverConfig()
        self.config.validate()

        self.device_manager = device_manager or SDRDeviceManager()
        self.sample_provider = sample_provider

        self.state = ReceiverState.IDLE
        self.device: SDRDevice | None = None
        self._started_at: float | None = None

    @property
    def is_receiving(self) -> bool:
        """Return whether the receiver is actively receiving."""
        return self.state == ReceiverState.RECEIVING

    @property
    def uptime_seconds(self) -> float:
        """Return receiver uptime in seconds."""
        if self._started_at is None:
            return 0.0

        return max(0.0, time.monotonic() - self._started_at)

    def discover_device(self) -> SDRDevice | None:
        """Discover and select the configured SDR device."""
        devices = self.device_manager.discover()

        if not devices:
            LOGGER.info("No SDR devices detected.")
            self.state = ReceiverState.READY
            return None

        try:
            device = normalize_device_index(
                self.config.device_index,
                devices,
            )
        except ValueError:
            LOGGER.warning(
                "Configured SDR device index %d was not found.",
                self.config.device_index,
            )
            self.state = ReceiverState.ERROR
            return None

        self.device = device
        self.state = ReceiverState.READY

        LOGGER.info("Selected SDR device: %s", device.identifier)

        return device

    def start(self) -> None:
        """
        Start receiving.

        The receiver can operate in software/replay mode when a
        sample provider has been supplied.
        """
        if self.state == ReceiverState.RECEIVING:
            return

        if self.device is None and self.sample_provider is None:
            self.discover_device()

        self.state = ReceiverState.RECEIVING
        self._started_at = time.monotonic()

        LOGGER.info(
            "Receiver started at %.0f Hz center frequency.",
            self.config.center_frequency_hz,
        )

    def stop(self) -> None:
        """Stop the receiver."""
        if self.state != ReceiverState.RECEIVING:
            self.state = ReceiverState.STOPPED
            return

        self.state = ReceiverState.STOPPED
        self._started_at = None

        LOGGER.info("Receiver stopped.")

    def capture(self, sample_count: int) -> IQSampleBuffer:
        """
        Capture a block of IQ samples.

        Args:
            sample_count: Number of complex samples requested.

        Returns:
            IQSampleBuffer containing the captured samples.

        Raises:
            ValueError: If sample_count is invalid.
            RuntimeError: If no sample provider is configured.
        """
        if sample_count <= 0:
            raise ValueError("sample_count must be greater than zero.")

        if not self.is_receiving:
            raise RuntimeError("Receiver is not running.")

        if self.sample_provider is None:
            raise RuntimeError(
                "No sample provider is configured. "
                "Connect an SDR backend or provide a replay source."
            )

        samples = tuple(self.sample_provider(sample_count))

        if len(samples) > sample_count:
            samples = samples[:sample_count]

        return IQSampleBuffer.from_iterable(
            samples=samples,
            sample_rate_hz=self.config.sample_rate_hz,
            center_frequency_hz=self.config.center_frequency_hz,
            sample_format=IQSampleFormat.COMPLEX64,
        )

    def reconfigure(self, config: ReceiverConfig) -> None:
        """Replace receiver configuration."""
        config.validate()

        if self.is_receiving:
            raise RuntimeError(
                "Stop the receiver before changing its configuration."
            )

        self.config = config
        self.device = None
        self.state = ReceiverState.IDLE

    def status(self) -> dict[str, object]:
        """Return a serializable receiver status snapshot."""
        return {
            "state": self.state.value,
            "device": (
                self.device.identifier
                if self.device is not None
                else None
            ),
            "center_frequency_hz": self.config.center_frequency_hz,
            "sample_rate_hz": self.config.sample_rate_hz,
            "gain": self.config.gain,
            "ppm_correction": self.config.ppm_correction,
            "device_index": self.config.device_index,
            "receiving": self.is_receiving,
            "uptime_seconds": round(self.uptime_seconds, 3),
        }
