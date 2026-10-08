"""
SDR device discovery and device management for OrbitWatch.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum


class SDRDeviceState(str, Enum):
    """Current state of an SDR device."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass(frozen=True)
class SDRDevice:
    """Description of an SDR device."""

    index: int
    name: str
    driver: str
    serial: str | None = None
    state: SDRDeviceState = SDRDeviceState.UNKNOWN

    @property
    def identifier(self) -> str:
        """Return a human-readable device identifier."""

        if self.serial:
            return f"{self.name} ({self.serial})"

        return f"{self.name} [{self.index}]"


class SDRDeviceManager:
    """Discover and manage locally available SDR devices."""

    def __init__(self) -> None:
        self.devices: tuple[SDRDevice, ...] = ()

    def discover(self) -> tuple[SDRDevice, ...]:
        """
        Discover available SDR devices.

        rtl_test is preferred when available. If rtl_test cannot
        discover anything, USB enumeration is used as a fallback.
        """

        devices = self._discover_with_rtl_test()

        if not devices:
            devices = self._discover_usb_candidates()

        self.devices = tuple(devices)

        return self.devices

    def get_device(
        self,
        index: int,
    ) -> SDRDevice | None:
        """Return a discovered device by index."""

        for device in self.devices:
            if device.index == index:
                return device

        return None

    def refresh(self) -> tuple[SDRDevice, ...]:
        """Refresh the device list."""

        return self.discover()

    @staticmethod
    def _discover_with_rtl_test() -> list[SDRDevice]:
        """Discover RTL-SDR devices using rtl_test."""

        executable = shutil.which("rtl_test")

        if executable is None:
            return []

        try:
            result = subprocess.run(
                [
                    executable,
                    "-t",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return []

        output = "\n".join(
            part
            for part in (
                result.stdout,
                result.stderr,
            )
            if part
        )

        return _parse_rtl_test_output(output)

    @staticmethod
    def _discover_usb_candidates() -> list[SDRDevice]:
        """
        Discover SDR-looking USB devices using lsusb.

        This is a lightweight fallback and does not claim that the
        device is actually usable by the SDR backend.
        """

        executable = shutil.which("lsusb")

        if executable is None:
            return []

        try:
            result = subprocess.run(
                [
                    executable,
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return []

        keywords = (
            "rtl2832",
            "rtl-sdr",
            "realtek semiconductor",
            "airspy",
            "hackrf",
            "sdrplay",
            "funcube",
        )

        devices: list[SDRDevice] = []

        for line in result.stdout.splitlines():
            lowered = line.lower()

            if not any(
                keyword in lowered
                for keyword in keywords
            ):
                continue

            devices.append(
                SDRDevice(
                    index=len(devices),
                    name=line.strip(),
                    driver="usb-detected",
                    state=SDRDeviceState.AVAILABLE,
                )
            )

        return devices


def _parse_rtl_test_output(
    output: str,
) -> list[SDRDevice]:
    """
    Parse device listings from rtl_test output.

    Supported formats include:

        0: RTLSDRBlog, Blog V4, SN: ABC123
        1: Generic RTL2832U OEM

    and:

        Device #0: RTL-SDR
        Device #2: Test SDR

    Unrelated or malformed lines are ignored.
    """

    devices: list[SDRDevice] = []

    # Format:
    #
    #     0: RTLSDRBlog, Blog V4, SN: ABC123
    #
    numbered_pattern = re.compile(
        r"^\s*(\d+)\s*:\s*(.+?)\s*$"
    )

    # Format:
    #
    #     Device #2: Test SDR
    #
    device_pattern = re.compile(
        r"^\s*Device\s+#(\d+)\s*:\s*(.+?)\s*$",
        flags=re.IGNORECASE,
    )

    for line in output.splitlines():
        line = line.strip()

        if not line:
            continue

        match = numbered_pattern.match(line)

        if match is None:
            match = device_pattern.match(line)

        if match is None:
            continue

        index = int(match.group(1))
        description = match.group(2).strip()

        if not description:
            continue

        serial: str | None = None

        serial_match = re.search(
            r"(?:,\s*)?(?:SN|Serial(?:\s+Number)?)\s*:\s*([^\s,]+)",
            description,
            flags=re.IGNORECASE,
        )

        if serial_match:
            serial = serial_match.group(1)

        devices.append(
            SDRDevice(
                index=index,
                name=description,
                driver="rtl-sdr",
                serial=serial,
                state=SDRDeviceState.AVAILABLE,
            )
        )

    return devices


def normalize_device_index(
    index: int,
    devices: list[SDRDevice] | tuple[SDRDevice, ...],
) -> SDRDevice:
    """
    Select an SDR device by its numeric index.

    Raises:
        ValueError: if the requested device does not exist.
    """

    for device in devices:
        if device.index == index:
            return device

    raise ValueError(
        f"SDR device index {index} was not found"
    )
