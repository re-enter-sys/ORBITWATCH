from __future__ import annotations

import pytest

from groundstation.protocols.kiss import (
    KISSFrame,
    KISSFrameType,
    KISSParser,
    encode_kiss_frame,
)


def test_kiss_frame_default_command() -> None:
    frame = KISSFrame(
        command=0,
        payload=b"hello",
    )

    assert frame.command == 0
    assert frame.payload == b"hello"


def test_kiss_frame_data_type() -> None:
    frame = KISSFrame(
        command=KISSFrameType.DATA.value,
        payload=b"payload",
    )

    assert frame.command == 0
    assert frame.payload == b"payload"


def test_kiss_frame_accepts_empty_payload() -> None:
    frame = KISSFrame(
        command=0,
        payload=b"",
    )

    assert frame.command == 0
    assert frame.payload == b""


def test_kiss_frame_type_values() -> None:
    assert KISSFrameType.DATA.value == 0


def test_encode_kiss_frame_basic() -> None:
    encoded = encode_kiss_frame(
        b"hello",
    )

    assert encoded[0] == 0xC0
    assert encoded[-1] == 0xC0
    assert encoded[1] == 0x00
    assert encoded[2:-1] == b"hello"


def test_encode_kiss_frame_with_command() -> None:
    encoded = encode_kiss_frame(
        b"hello",
        command=1,
    )

    assert encoded[0] == 0xC0
    assert encoded[-1] == 0xC0
    assert encoded[1] == 0x01
    assert encoded[2:-1] == b"hello"


def test_encode_kiss_frame_escapes_fend() -> None:
    encoded = encode_kiss_frame(
        b"A\xC0B",
    )

    assert encoded == bytes(
        [
            0xC0,
            0x00,
            ord("A"),
            0xDB,
            0xDC,
            ord("B"),
            0xC0,
        ]
    )


def test_encode_kiss_frame_escapes_fesc() -> None:
    encoded = encode_kiss_frame(
        b"A\xDBB",
    )

    assert encoded == bytes(
        [
            0xC0,
            0x00,
            ord("A"),
            0xDB,
            0xDD,
            ord("B"),
            0xC0,
        ]
    )


def test_encode_kiss_frame_escapes_both_special_bytes() -> None:
    encoded = encode_kiss_frame(
        b"\xC0\xDB",
    )

    assert encoded == bytes(
        [
            0xC0,
            0x00,
            0xDB,
            0xDC,
            0xDB,
            0xDD,
            0xC0,
        ]
    )


def test_encode_kiss_frame_rejects_invalid_payload() -> None:
    with pytest.raises(TypeError):
        encode_kiss_frame("hello")  # type: ignore[arg-type]


def test_parser_parses_single_frame() -> None:
    parser = KISSParser()

    frames = parser.feed(
        encode_kiss_frame(b"hello")
    )

    assert len(frames) == 1
    assert frames[0].payload == b"hello"
    assert frames[0].command == 0


def test_parser_parses_multiple_frames() -> None:
    parser = KISSParser()

    data = (
        encode_kiss_frame(b"first")
        + encode_kiss_frame(b"second")
        + encode_kiss_frame(b"third")
    )

    frames = parser.feed(data)

    assert len(frames) == 3
    assert [frame.payload for frame in frames] == [
        b"first",
        b"second",
        b"third",
    ]


def test_parser_handles_fragmented_frame() -> None:
    parser = KISSParser()

    encoded = encode_kiss_frame(b"fragmented")

    first = parser.feed(encoded[:3])
    second = parser.feed(encoded[3:])

    assert first == []
    assert len(second) == 1
    assert second[0].payload == b"fragmented"


def test_parser_handles_one_byte_at_a_time() -> None:
    parser = KISSParser()

    encoded = encode_kiss_frame(b"slow stream")

    frames = []

    for byte in encoded:
        frames.extend(parser.feed(bytes([byte])))

    assert len(frames) == 1
    assert frames[0].payload == b"slow stream"


def test_parser_unescapes_fend() -> None:
    parser = KISSParser()

    frames = parser.feed(
        encode_kiss_frame(b"A\xC0B")
    )

    assert len(frames) == 1
    assert frames[0].payload == b"A\xC0B"


def test_parser_unescapes_fesc() -> None:
    parser = KISSParser()

    frames = parser.feed(
        encode_kiss_frame(b"A\xDBB")
    )

    assert len(frames) == 1
    assert frames[0].payload == b"A\xDBB"


def test_parser_preserves_command() -> None:
    parser = KISSParser()

    encoded = encode_kiss_frame(
        b"command",
        command=1,
    )

    frames = parser.feed(encoded)

    assert len(frames) == 1
    assert frames[0].command == 1
    assert frames[0].payload == b"command"


def test_parser_handles_command_bits() -> None:
    parser = KISSParser()

    encoded = encode_kiss_frame(
        b"command",
        command=0x20,
    )

    frames = parser.feed(encoded)

    assert len(frames) == 1
    assert frames[0].command == 0x20
    assert frames[0].payload == b"command"


def test_parser_empty_frame() -> None:
    parser = KISSParser()

    frames = parser.feed(b"\xC0\xC0")

    assert frames == []


def test_parser_handles_partial_frame() -> None:
    parser = KISSParser()

    encoded = encode_kiss_frame(b"payload")

    first = parser.feed(encoded[:4])

    assert first == []

    second = parser.feed(encoded[4:])

    assert len(second) == 1
    assert second[0].payload == b"payload"


def test_parser_accepts_empty_input() -> None:
    parser = KISSParser()

    assert parser.feed(b"") == []


def test_parser_rejects_invalid_byte_values() -> None:
    parser = KISSParser()

    with pytest.raises(ValueError):
        parser.feed([256])


def test_parser_round_trip_binary_payload() -> None:
    parser = KISSParser()

    payload = bytes(range(256))

    frames = parser.feed(
        encode_kiss_frame(payload)
    )

    assert len(frames) == 1
    assert frames[0].payload == payload


def test_parser_round_trip_special_bytes() -> None:
    parser = KISSParser()

    payload = b"\x00\x01\xC0\x02\xDB\x03\xFF"

    frames = parser.feed(
        encode_kiss_frame(payload)
    )

    assert len(frames) == 1
    assert frames[0].payload == payload


def test_encode_parse_round_trip_with_command() -> None:
    parser = KISSParser()

    payload = b"AX25 TEST DATA"

    encoded = encode_kiss_frame(
        payload,
        command=3,
    )

    frames = parser.feed(encoded)

    assert len(frames) == 1
    assert frames[0].command == 3
    assert frames[0].payload == payload


def test_parser_reset() -> None:
    parser = KISSParser()

    encoded = encode_kiss_frame(b"payload")

    parser.feed(encoded[:4])

    parser.reset()

    frames = parser.feed(encoded)

    assert len(frames) == 1
    assert frames[0].payload == b"payload"


def test_parser_multiple_frames_after_fragmentation() -> None:
    parser = KISSParser()

    first = encode_kiss_frame(b"first")
    second = encode_kiss_frame(b"second")

    data = first + second

    frames = []

    frames.extend(parser.feed(data[:5]))
    frames.extend(parser.feed(data[5:]))

    assert [frame.payload for frame in frames] == [
        b"first",
        b"second",
    ]
