"""
Tests for the OrbitWatch AX.25 protocol subsystem.
"""

from __future__ import annotations

import pytest

from groundstation.protocols import (
    AX25Address,
    AX25Frame,
    AX25Parser,
    encode_ax25_address,
    encode_ax25_ui_frame,
)


def test_ax25_address_creation() -> None:
    address = AX25Address(
        callsign="N0CALL",
        ssid=1,
    )

    assert address.callsign == "N0CALL"
    assert address.ssid == 1
    assert address.display == "N0CALL-1"


def test_ax25_address_without_ssid() -> None:
    address = AX25Address(
        callsign="N0CALL",
    )

    assert address.display == "N0CALL"


def test_ax25_address_normalizes_callsign() -> None:
    address = AX25Address(
        callsign="n0call",
    )

    assert address.callsign == "N0CALL"


def test_ax25_address_rejects_empty_callsign() -> None:
    with pytest.raises(ValueError):
        AX25Address(callsign="")


def test_ax25_address_rejects_long_callsign() -> None:
    with pytest.raises(ValueError):
        AX25Address(
            callsign="TOOLONG"
        )


def test_ax25_address_rejects_invalid_ssid() -> None:
    with pytest.raises(ValueError):
        AX25Address(
            callsign="N0CALL",
            ssid=-1,
        )

    with pytest.raises(ValueError):
        AX25Address(
            callsign="N0CALL",
            ssid=16,
        )


def test_ax25_address_command_response_flags() -> None:
    address = AX25Address(
        callsign="N0CALL",
        command=True,
        response=True,
    )

    assert address.command is True
    assert address.response is True


def test_encode_ax25_address() -> None:
    address = AX25Address(
        callsign="N0CALL",
        ssid=1,
    )

    encoded = encode_ax25_address(
        address,
        final=True,
    )

    assert len(encoded) == 7

    assert encoded[:6] == bytes(
        [
            ord("N") << 1,
            ord("0") << 1,
            ord("C") << 1,
            ord("A") << 1,
            ord("L") << 1,
            ord("L") << 1,
        ]
    )

    assert encoded[6] & 0x01


def test_encode_ax25_address_non_final() -> None:
    address = AX25Address(
        callsign="N0CALL",
    )

    encoded = encode_ax25_address(
        address,
        final=False,
    )

    assert len(encoded) == 7
    assert encoded[6] & 0x01 == 0


def test_ax25_address_encode_decode_round_trip() -> None:
    address = AX25Address(
        callsign="N0CALL",
        ssid=7,
        command=True,
        response=False,
    )

    encoded = encode_ax25_address(
        address,
        final=True,
    )

    parser = AX25Parser()

    decoded, next_offset, final = parser._parse_address(
        encoded,
        0,
    )

    assert next_offset == 7
    assert final is True

    assert decoded.callsign == address.callsign
    assert decoded.ssid == address.ssid


def test_ax25_frame_creation() -> None:
    destination = AX25Address(
        callsign="APRS",
    )

    source = AX25Address(
        callsign="N0CALL",
    )

    frame = AX25Frame(
        destination=destination,
        source=source,
        digipeaters=(),
        control=0x03,
        pid=0xF0,
        information=b"HELLO",
    )

    assert frame.destination == destination
    assert frame.source == source
    assert frame.digipeaters == ()
    assert frame.control == 0x03
    assert frame.pid == 0xF0
    assert frame.information == b"HELLO"


def test_ax25_frame_is_ui_frame() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(),
        control=0x03,
        pid=0xF0,
        information=b"TEST",
    )

    assert frame.is_ui_frame is True


def test_ax25_frame_non_ui() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(),
        control=0x13,
        pid=0xF0,
        information=b"TEST",
    )

    assert frame.is_ui_frame is False


def test_ax25_frame_information_length() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(),
        control=0x03,
        pid=0xF0,
        information=b"HELLO",
    )

    assert frame.information_length == 5


def test_ax25_frame_payload_text() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(),
        control=0x03,
        pid=0xF0,
        information=b"HELLO",
    )

    assert frame.payload_text == "HELLO"


def test_ax25_frame_payload_text_invalid_utf8() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(),
        control=0x03,
        pid=0xF0,
        information=b"\xff\xfe",
    )

    assert "\ufffd" in frame.payload_text


def test_ax25_frame_path_without_digipeaters() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(),
        control=0x03,
        pid=0xF0,
        information=b"TEST",
    )

    assert frame.path == ()


def test_ax25_frame_path_with_digipeaters() -> None:
    frame = AX25Frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        digipeaters=(
            AX25Address("WIDE1", ssid=1),
            AX25Address("WIDE2", ssid=2),
        ),
        control=0x03,
        pid=0xF0,
        information=b"TEST",
    )

    assert frame.path == (
        "WIDE1-1",
        "WIDE2-2",
    )


def test_encode_ax25_ui_frame() -> None:
    encoded = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        information=b"HELLO",
    )

    assert isinstance(encoded, bytes)
    assert len(encoded) == 7 + 7 + 2 + 5

    assert encoded[6] & 0x01 == 0
    assert encoded[13] & 0x01 == 1

    assert encoded[14] == 0x03
    assert encoded[15] == 0xF0
    assert encoded[16:] == b"HELLO"


def test_encode_ax25_ui_frame_with_digipeaters() -> None:
    encoded = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        information=b"HELLO",
        digipeaters=(
            AX25Address("WIDE1", ssid=1),
            AX25Address("WIDE2", ssid=2),
        ),
    )

    assert encoded[6] & 0x01 == 0
    assert encoded[13] & 0x01 == 0
    assert encoded[20] & 0x01 == 0
    assert encoded[27] & 0x01 == 1

    assert encoded[28] == 0x03
    assert encoded[29] == 0xF0
    assert encoded[30:] == b"HELLO"


def test_ax25_encode_parse_round_trip() -> None:
    destination = AX25Address(
        callsign="APRS",
    )

    source = AX25Address(
        callsign="N0CALL",
        ssid=7,
    )

    digipeaters = (
        AX25Address(
            callsign="WIDE1",
            ssid=1,
        ),
        AX25Address(
            callsign="WIDE2",
            ssid=2,
        ),
    )

    payload = b"OrbitWatch AX25 test"

    encoded = encode_ax25_ui_frame(
        destination=destination,
        source=source,
        information=payload,
        digipeaters=digipeaters,
    )

    decoded = AX25Parser().parse(
        encoded,
    )

    assert decoded.destination.callsign == destination.callsign
    assert decoded.destination.ssid == destination.ssid

    assert decoded.source.callsign == source.callsign
    assert decoded.source.ssid == source.ssid

    assert len(decoded.digipeaters) == 2

    assert decoded.digipeaters[0].callsign == "WIDE1"
    assert decoded.digipeaters[0].ssid == 1

    assert decoded.digipeaters[1].callsign == "WIDE2"
    assert decoded.digipeaters[1].ssid == 2
    assert decoded.control == 0x03
    assert decoded.pid == 0xF0
    assert decoded.information == payload
    assert decoded.is_ui_frame
    assert decoded.payload_text == (
        "OrbitWatch AX25 test"
    )


def test_ax25_parser_minimum_frame_validation() -> None:
    with pytest.raises(ValueError):
        AX25Parser().parse(
            b"",
        )

    with pytest.raises(ValueError):
        AX25Parser().parse(
            b"\x00" * 15,
        )


def test_ax25_parser_requires_destination_final_bit_clear() -> None:
    destination = bytearray(
        encode_ax25_address(
            AX25Address("APRS"),
            final=True,
        )
    )

    source = encode_ax25_address(
        AX25Address("N0CALL"),
        final=True,
    )

    frame = bytes(
        destination
        + source
        + bytes([0x03, 0xF0])
        + b"TEST"
    )

    with pytest.raises(ValueError):
        AX25Parser().parse(frame)


def test_ax25_parser_requires_control_and_pid() -> None:
    destination = encode_ax25_address(
        AX25Address("APRS"),
        final=False,
    )

    source = encode_ax25_address(
        AX25Address("N0CALL"),
        final=True,
    )

    frame = destination + source

    with pytest.raises(ValueError):
        AX25Parser().parse(frame)


def test_ax25_parser_rejects_truncated_address() -> None:
    with pytest.raises(ValueError):
        AX25Parser()._parse_address(
            b"\x00" * 6,
            0,
        )


def test_ax25_parser_handles_empty_information() -> None:
    encoded = encode_ax25_ui_frame(
        destination=AX25Address("APRS"),
        source=AX25Address("N0CALL"),
        information=b"",
    )

    decoded = AX25Parser().parse(
        encoded,
    )

    assert decoded.information == b""
    assert decoded.information_length == 0
    assert decoded.payload_text == ""
