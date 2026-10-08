"""
AX.25 frame parsing.

AX.25 is a packet radio protocol widely associated with amateur
radio and satellite packet communication.

This implementation focuses on the packet-decoding path:

    KISS payload -> AX.25 addresses/control/PID -> information

It supports standard 7-byte AX.25 address fields and validates
the basic frame structure before exposing decoded information.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


AX25_ADDRESS_LENGTH = 7
AX25_MIN_FRAME_LENGTH = 16


@dataclass(frozen=True)
class AX25Address:
    """Decoded AX.25 callsign/address."""

    callsign: str
    ssid: int = 0
    command: bool = False
    response: bool = False

    def __post_init__(self) -> None:
        callsign = self.callsign.strip().upper()

        if not callsign:
            raise ValueError("AX.25 callsign cannot be empty.")

        if len(callsign) > 6:
            raise ValueError(
                "AX.25 callsign cannot exceed six characters."
            )

        if self.ssid < 0 or self.ssid > 15:
            raise ValueError(
                "AX.25 SSID must be between 0 and 15."
            )

        object.__setattr__(self, "callsign", callsign)

    @property
    def display(self) -> str:
        """Return the callsign in standard SSID notation."""
        if self.ssid:
            return f"{self.callsign}-{self.ssid}"

        return self.callsign


@dataclass(frozen=True)
class AX25Frame:
    """Decoded AX.25 UI frame."""

    destination: AX25Address
    source: AX25Address
    digipeaters: tuple[AX25Address, ...]
    control: int
    pid: int
    information: bytes

    @property
    def is_ui_frame(self) -> bool:
        """Return whether the frame is an AX.25 UI frame."""
        return self.control == 0x03

    @property
    def information_length(self) -> int:
        """Return the information payload length."""
        return len(self.information)

    @property
    def payload_text(self) -> str:
        """Decode the information field as UTF-8."""
        return self.information.decode(
            "utf-8",
            errors="replace",
        )

    @property
    def path(self) -> tuple[str, ...]:
        """Return the digipeater path."""
        return tuple(
            address.display
            for address in self.digipeaters
        )


class AX25Parser:
    """Parser for raw AX.25 frames."""

    def parse(
        self,
        frame: bytes | bytearray | Iterable[int],
    ) -> AX25Frame:
        """
        Parse a raw AX.25 frame.

        Args:
            frame: Raw AX.25 bytes.

        Returns:
            Decoded AX25Frame.

        Raises:
            ValueError: If the frame structure is invalid.
        """
        data = bytes(frame)

        if len(data) < AX25_MIN_FRAME_LENGTH:
            raise ValueError(
                "AX.25 frame is too short."
            )

        position = 0

        destination, position, destination_final = (
            self._parse_address(
                data,
                position,
            )
        )

        if destination_final:
            raise ValueError(
                "AX.25 destination address cannot terminate "
                "the address list."
            )

        source, position, source_final = (
            self._parse_address(
                data,
                position,
            )
        )

        digipeaters: list[AX25Address] = []

        # The least significant bit of the seventh address byte
        # is the AX.25 address-extension bit.
        #
        # 1 = this is the final address field
        # 0 = another address field follows
        while not source_final:
            address, position, source_final = (
                self._parse_address(
                    data,
                    position,
                )
            )

            digipeaters.append(address)

        # A valid AX.25 frame must have control + PID after the
        # address section.
        if position + 2 > len(data):
            raise ValueError(
                "AX.25 frame is missing control/PID fields."
            )

        control = data[position]
        pid = data[position + 1]
        information = data[position + 2:]

        return AX25Frame(
            destination=destination,
            source=source,
            digipeaters=tuple(digipeaters),
            control=control,
            pid=pid,
            information=information,
        )

    @staticmethod
    def _parse_address(
        data: bytes,
        offset: int,
    ) -> tuple[AX25Address, int, bool]:
        """
        Parse one seven-byte AX.25 address field.

        Returns:

            address
            next byte offset
            whether this was the final address
        """
        end = offset + AX25_ADDRESS_LENGTH

        if offset < 0 or end > len(data):
            raise ValueError(
                "AX.25 address extends beyond frame boundary."
            )

        address_bytes = data[offset:end]

        callsign_chars: list[str] = []

        for value in address_bytes[:6]:
            character = chr(value >> 1)
            callsign_chars.append(character)

        callsign = "".join(callsign_chars).rstrip()

        if not callsign:
            raise ValueError(
                "AX.25 address contains an empty callsign."
            )

        ssid_byte = address_bytes[6]

        ssid = (ssid_byte >> 1) & 0x0F

        command = bool(ssid_byte & 0x80)
        response = bool(ssid_byte & 0x40)

        final = bool(ssid_byte & 0x01)

        address = AX25Address(
            callsign=callsign,
            ssid=ssid,
            command=command,
            response=response,
        )

        return address, end, final


def encode_ax25_address(
    address: AX25Address,
    final: bool = True,
) -> bytes:
    """
    Encode an AX.25 address field.

    Args:
        address: AX.25 address.
        final: Whether this is the final address field.

    Returns:
        Seven-byte AX.25 address.
    """
    callsign = address.callsign.upper().ljust(6)

    if len(callsign) != 6:
        raise ValueError(
            "AX.25 callsign must contain between one and six characters."
        )

    result = bytearray(
        ord(character) << 1
        for character in callsign
    )

    ssid_byte = 0x60 | ((address.ssid & 0x0F) << 1)

    if address.command:
        ssid_byte |= 0x80

    if address.response:
        ssid_byte |= 0x40

    if final:
        ssid_byte |= 0x01

    result.append(ssid_byte)

    return bytes(result)


def encode_ax25_ui_frame(
    destination: AX25Address,
    source: AX25Address,
    information: bytes,
    digipeaters: Iterable[AX25Address] = (),
    pid: int = 0xF0,
) -> bytes:
    """
    Build an AX.25 UI frame.

    Args:
        destination: Destination callsign.
        source: Source callsign.
        information: Information field.
        digipeaters: Optional digipeater path.
        pid: Protocol identifier.

    Returns:
        Raw AX.25 UI frame.
    """
    if not isinstance(information, bytes):
        raise TypeError(
            "information must be bytes."
        )

    if not 0 <= pid <= 255:
        raise ValueError(
            "pid must be between 0 and 255."
        )

    path = tuple(digipeaters)

    result = bytearray()

    # Destination is never the final address because source follows.
    result.extend(
        encode_ax25_address(
            destination,
            final=False,
        )
    )

    # Source is final only when no digipeater path exists.
    result.extend(
        encode_ax25_address(
            source,
            final=not path,
        )
    )

    for index, address in enumerate(path):
        result.extend(
            encode_ax25_address(
                address,
                final=index == len(path) - 1,
            )
        )

    # AX.25 UI control field.
    result.append(0x03)

    # Protocol identifier.
    result.append(pid)

    # Information field.
    result.extend(information)

    return bytes(result)
