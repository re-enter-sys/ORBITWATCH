"""
Protocol decoding subsystem for OrbitWatch.

Provides KISS framing, AX.25 packet decoding, and a generic
telemetry payload representation.
"""

from .ax25 import (
    AX25Address,
    AX25Frame,
    AX25Parser,
    encode_ax25_address,
    encode_ax25_ui_frame,
)
from .kiss import (
    KISSFrame,
    KISSFrameType,
    KISSParser,
    encode_kiss_frame,
)
from .telemetry import (
    TelemetryField,
    TelemetryPacket,
    TelemetryParser,
    fields_from_mapping,
)

__all__ = [
    "AX25Address",
    "AX25Frame",
    "AX25Parser",
    "encode_ax25_address",
    "encode_ax25_ui_frame",
    "KISSFrame",
    "KISSFrameType",
    "KISSParser",
    "encode_kiss_frame",
    "TelemetryField",
    "TelemetryPacket",
    "TelemetryParser",
    "fields_from_mapping",
]
