from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..protocols.ax25 import AX25Address, encode_ax25_ui_frame
from ..protocols.kiss import KISSFrameType, encode_kiss_frame
from ..recording.models import RecordingEvent


DEMO_SATELLITE = "OW-DEMO"
DEMO_SOURCE = "OWDEMO"
DEMO_DESTINATION = "APRS"

DEMO_TELEMETRY = (
    b"TEMP=23.5,BATT=7.4,MODE=SAFE",
    b"TEMP=23.7,BATT=7.3,MODE=SAFE",
    b"TEMP=23.9,BATT=7.2,MODE=SAFE",
)


def _build_kiss_packet(information: bytes) -> bytes:
    """Build one real AX.25 UI frame wrapped in a KISS DATA frame."""
    ax25 = encode_ax25_ui_frame(
        destination=AX25Address(DEMO_DESTINATION),
        source=AX25Address(DEMO_SOURCE),
        information=information,
    )

    return encode_kiss_frame(
        ax25,
        command=KISSFrameType.DATA,
    )


def build_demo_events(
    *,
    start_time: datetime | None = None,
) -> list[RecordingEvent]:
    """
    Build controlled development/replay events.

    These packets are intentionally synthetic development data. They are
    not presented as real satellite telemetry or historical observations.
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    events: list[RecordingEvent] = []

    for index, information in enumerate(DEMO_TELEMETRY, start=1):
        timestamp = start_time + timedelta(seconds=(index - 1) * 5)
        kiss_packet = _build_kiss_packet(information)

        payload: dict[str, Any] = {
            "mode": "REPLAY",
            "development": True,
            "protocol": "KISS/AX.25",
            "satellite": DEMO_SATELLITE,
            "source": DEMO_SOURCE,
            "destination": DEMO_DESTINATION,
            "packet_sequence": index,
            "kiss_hex": kiss_packet.hex(),
        }

        events.append(
            RecordingEvent(
                timestamp=timestamp.isoformat(),
                event_type="KISS_FRAME",
                payload=payload,
            )
        )

    return events
