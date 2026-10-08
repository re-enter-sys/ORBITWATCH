"""
KISS protocol framing.

KISS (Keep It Simple Stupid) is commonly used to transport
AX.25 frames between a host computer and a TNC or software
radio modem.

KISS special bytes:

    FEND  = 0xC0
    FESC  = 0xDB
    TFEND = 0xDC
    TFESC = 0xDD

OrbitWatch implements the framing/escaping layer independently
from the physical radio interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD


class KISSFrameType(IntEnum):
    """KISS command/frame types."""

    DATA = 0x00
    TX_DELAY = 0x01
    P = 0x02
    SLOT_TIME = 0x03
    TX_TAIL = 0x04
    FULL_DUPLEX = 0x05
    SET_HARDWARE = 0x06
    RETURN = 0xFF


@dataclass(frozen=True)
class KISSFrame:
    """Decoded KISS frame."""

    command: int
    payload: bytes

    @property
    def frame_type(self) -> KISSFrameType | None:
        """Return the known KISS frame type, if recognized."""
        try:
            return KISSFrameType(self.command)
        except ValueError:
            return None

    @property
    def is_data(self) -> bool:
        """Return True when this is a KISS data frame."""
        return (self.command & 0x0F) == KISSFrameType.DATA


class KISSParser:
    """
    Stateful KISS frame parser.

    The parser accepts arbitrary chunks of bytes, allowing it to
    process data arriving incrementally from a serial device,
    TCP stream, replay file, or other transport.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._escaping = False

    def reset(self) -> None:
        """Reset the parser state."""
        self._buffer.clear()
        self._escaping = False

    def feed(self, data: Iterable[int] | bytes) -> list[KISSFrame]:
        """
        Feed bytes into the parser.

        Args:
            data: Incoming KISS byte stream.

        Returns:
            All complete KISS frames decoded from the input.
        """
        frames: list[KISSFrame] = []

        for raw_value in data:
            value = int(raw_value)

            if not 0 <= value <= 255:
                raise ValueError("KISS byte values must be between 0 and 255.")

            if value == FEND:
                if self._buffer:
                    frame = self._decode_buffer()
                    if frame is not None:
                        frames.append(frame)

                self._buffer.clear()
                self._escaping = False
                continue

            if self._escaping:
                if value == TFEND:
                    self._buffer.append(FEND)
                elif value == TFESC:
                    self._buffer.append(FESC)
                else:
                    # Invalid escape sequence. Keep the byte so that
                    # malformed input does not silently disappear.
                    self._buffer.append(value)

                self._escaping = False
                continue

            if value == FESC:
                self._escaping = True
                continue

            self._buffer.append(value)

        return frames

    def flush(self) -> KISSFrame | None:
        """
        Decode the currently buffered frame.

        This is mainly useful for replay/testing sources that may
        not contain a trailing FEND byte.
        """
        if not self._buffer:
            return None

        frame = self._decode_buffer()
        self._buffer.clear()
        self._escaping = False

        return frame

    def _decode_buffer(self) -> KISSFrame | None:
        """Convert the current raw buffer into a KISS frame."""
        if not self._buffer:
            return None

        command = self._buffer[0]
        payload = bytes(self._buffer[1:])

        return KISSFrame(
            command=command,
            payload=payload,
        )


def encode_kiss_frame(
    payload: bytes,
    command: int = KISSFrameType.DATA,
) -> bytes:
    """
    Encode a payload into a KISS frame.

    The function is useful for deterministic replay/test data and
    for future transport integrations.

    Args:
        payload: Frame payload.
        command: KISS command byte.

    Returns:
        Complete FEND-delimited KISS frame.
    """
    if not 0 <= int(command) <= 255:
        raise ValueError("command must be between 0 and 255.")

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes.")

    encoded = bytearray()
    encoded.append(int(command))

    for value in payload:
        if value == FEND:
            encoded.extend((FESC, TFEND))
        elif value == FESC:
            encoded.extend((FESC, TFESC))
        else:
            encoded.append(value)

    return bytes((FEND,)) + bytes(encoded) + bytes((FEND,))
