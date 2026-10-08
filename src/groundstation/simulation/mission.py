from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..mission.models import (
    MissionEventSeverity,
    MissionEventType,
)
from ..mission.service import MissionLogService
from ..protocols.kiss import KISSParser
from ..recording.models import RecordingEvent
from ..recording.reader import EventRecordingReader
from ..recording.replay import ReplayController
from ..recording.service import RecordingService
from ..telemetry.database import TelemetryDatabase
from ..telemetry.engine import TelemetryEngine
from .samples import DEMO_SATELLITE, build_demo_events


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"


def _mission_database_path(data_root: Path) -> Path:
    return data_root / "mission" / "mission.db"


def _telemetry_database_path(data_root: Path) -> Path:
    return data_root / "telemetry" / "orbitwatch.db"


def _recording_root(data_root: Path) -> Path:
    return data_root / "recordings"


def _event_timestamp(event: RecordingEvent) -> datetime:
    """
    Convert the recording's serialized ISO-8601 timestamp into the
    timezone-aware datetime required by the telemetry engine.
    """
    value = event.timestamp

    if isinstance(value, datetime):
        timestamp = value

    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid replay event timestamp: {value!r}"
            ) from exc

    else:
        raise TypeError(
            "Replay event timestamp must be a datetime or ISO-8601 string."
        )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    return timestamp.astimezone(timezone.utc)


def _decode_replay_event(event: RecordingEvent) -> bytes:
    """Extract the encoded KISS frame from one recording event."""
    value = event.payload.get("kiss_hex")

    if not isinstance(value, str) or not value:
        raise ValueError(
            "Replay event does not contain a valid 'kiss_hex' payload."
        )

    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(
            "Replay event contains invalid hexadecimal KISS data."
        ) from exc


def run_demo(
    *,
    data_root: str | Path | None = None,
    speed: float = 1.0,
    realtime: bool = False,
) -> dict[str, Any]:
    """
    Run the controlled OrbitWatch development mission.

    The demo creates an actual event recording containing encoded
    KISS -> AX.25 -> telemetry packets, then replays those packets through
    the same protocol and telemetry processing stack used by the project.

    No dashboard values are hardcoded here.
    """
    if speed <= 0:
        raise ValueError("Replay speed must be greater than zero.")

    root = (
        Path(data_root)
        if data_root is not None
        else DEFAULT_DATA_ROOT
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    telemetry_path = _telemetry_database_path(root)
    mission_path = _mission_database_path(root)
    recording_root = _recording_root(root)

    telemetry_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    mission_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    recording_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------------
    # 1. Create a controlled event recording.
    # ---------------------------------------------------------------

    recording_service = RecordingService(
        recording_root
    )

    writer = recording_service.start_event_recording(
        satellite=DEMO_SATELLITE,
        description=(
            "OrbitWatch controlled development replay. "
            "Synthetic KISS/AX.25 telemetry for pipeline validation."
        ),
    )

    events = build_demo_events()

    writer.write_many(events)

    recording_metadata = writer.close()

    recording_id = recording_metadata.recording_id

    # ---------------------------------------------------------------
    # 2. Validate the completed recording before replaying it.
    # ---------------------------------------------------------------

    reader = EventRecordingReader(
        writer.data_path
    )

    if not reader.validate():
        raise RuntimeError(
            f"Recording validation failed: {writer.data_path}"
        )

    replay_events = list(
        reader.iter_events()
    )

    if not replay_events:
        raise RuntimeError(
            "The development recording contains no replay events."
        )

    # ---------------------------------------------------------------
    # 3. Open the real telemetry and mission databases.
    # ---------------------------------------------------------------

    telemetry_database = TelemetryDatabase(
        telemetry_path
    )

    telemetry_engine = TelemetryEngine(
        database=telemetry_database,
        persist=True,
    )

    mission_service = MissionLogService(
        mission_path
    )

    mission_service.start_mission(
        mode="REPLAY",
        satellite=DEMO_SATELLITE,
        metadata={
            "development": True,
            "replay": True,
            "recording_id": recording_id,
            "description": (
                "Controlled OrbitWatch development mission."
            ),
        },
    )

    mission_service.log(
        MissionEventType.REPLAY_STARTED,
        "Development replay started.",
        severity=MissionEventSeverity.INFO,
        satellite=DEMO_SATELLITE,
        recording_id=recording_id,
        payload={
            "mode": "REPLAY",
            "development": True,
            "recording_id": recording_id,
            "event_count": len(replay_events),
        },
    )

    kiss_parser = KISSParser()

    processed_packets = 0
    decoded_packets = 0
    failed_packets = 0

    # ---------------------------------------------------------------
    # 4. Feed replay events through the real protocol stack.
    # ---------------------------------------------------------------

    def process_event(event: RecordingEvent) -> None:
        nonlocal processed_packets
        nonlocal decoded_packets
        nonlocal failed_packets

        kiss_bytes = _decode_replay_event(event)

        frames = kiss_parser.feed(
            kiss_bytes
        )

        if not frames:
            failed_packets += 1

            mission_service.log(
                MissionEventType.PACKET_REJECTED,
                "Replay event contained no complete KISS frame.",
                severity=MissionEventSeverity.WARNING,
                satellite=DEMO_SATELLITE,
                recording_id=recording_id,
                payload={
                    "mode": "REPLAY",
                    "development": True,
                },
            )

            return

        timestamp = _event_timestamp(event)

        for frame in frames:
            processed_packets += 1

            packet_id = (
                f"{recording_id}:"
                f"{processed_packets:04d}"
            )

            mission_service.log(
                MissionEventType.PACKET_RECEIVED,
                "KISS packet received from replay.",
                severity=MissionEventSeverity.INFO,
                satellite=DEMO_SATELLITE,
                recording_id=recording_id,
                packet_id=packet_id,
                payload={
                    "mode": "REPLAY",
                    "development": True,
                    "protocol": "KISS/AX.25",
                    "packet_sequence": processed_packets,
                },
            )

            try:
                result = telemetry_engine.process_kiss(
                    frame,
                    satellite=DEMO_SATELLITE,
                    timestamp=timestamp,
                    source="replay",
                    packet_id=packet_id,
                    metadata={
                        "mode": "REPLAY",
                        "development": True,
                        "recording_id": recording_id,
                    },
                    persist=True,
                )

            except Exception as exc:
                failed_packets += 1

                mission_service.log(
                    MissionEventType.TELEMETRY_DECODE_ERROR,
                    "Telemetry decoding failed for replay packet.",
                    severity=MissionEventSeverity.ERROR,
                    satellite=DEMO_SATELLITE,
                    recording_id=recording_id,
                    packet_id=packet_id,
                    payload={
                        "mode": "REPLAY",
                        "development": True,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )

                return

            if result.valid and result.decoded is not None:
                decoded_packets += 1

                mission_service.log(
                    MissionEventType.TELEMETRY_RECEIVED,
                    "Telemetry decoded from replay packet.",
                    severity=MissionEventSeverity.SUCCESS,
                    satellite=DEMO_SATELLITE,
                    recording_id=recording_id,
                    packet_id=packet_id,
                    payload={
                        "mode": "REPLAY",
                        "development": True,
                        "field_count": result.field_count,
                        "values": result.decoded.to_dict(),
                    },
                )

            else:
                failed_packets += 1

                mission_service.log(
                    MissionEventType.TELEMETRY_DECODE_ERROR,
                    "Replay packet did not produce valid telemetry.",
                    severity=MissionEventSeverity.WARNING,
                    satellite=DEMO_SATELLITE,
                    recording_id=recording_id,
                    packet_id=packet_id,
                    payload={
                        "mode": "REPLAY",
                        "development": True,
                        "valid": result.valid,
                        "crc_ok": result.crc_ok,
                    },
                )

    # ---------------------------------------------------------------
    # 5. Run the real ReplayController.
    # ---------------------------------------------------------------

    replay_controller = ReplayController(
        speed=speed,
        realtime=realtime,
    )

    replay_status = replay_controller.replay_events(
        replay_events,
        process_event,
    )

    replay_status_dict = replay_status.to_dict()

    if replay_status.state.value == "completed":
        mission_service.log(
            MissionEventType.REPLAY_COMPLETED,
            "Development replay completed.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=DEMO_SATELLITE,
            recording_id=recording_id,
            payload={
                "mode": "REPLAY",
                "development": True,
                "packets_processed": processed_packets,
                "packets_decoded": decoded_packets,
                "packets_failed": failed_packets,
                "replay": replay_status_dict,
            },
        )

    elif replay_status.state.value == "stopped":
        mission_service.log(
            MissionEventType.REPLAY_STOPPED,
            "Development replay stopped.",
            severity=MissionEventSeverity.WARNING,
            satellite=DEMO_SATELLITE,
            recording_id=recording_id,
            payload={
                "mode": "REPLAY",
                "development": True,
                "replay": replay_status_dict,
            },
        )

    else:
        mission_service.log(
            MissionEventType.SYSTEM_ERROR,
            "Development replay ended with an error.",
            severity=MissionEventSeverity.ERROR,
            satellite=DEMO_SATELLITE,
            recording_id=recording_id,
            payload={
                "mode": "REPLAY",
                "development": True,
                "replay": replay_status_dict,
            },
        )

    mission_service.stop_mission(
        satellite=DEMO_SATELLITE,
    )

    telemetry_engine.close()
    mission_service.close()

    return {
        "mode": "REPLAY",
        "development": True,
        "satellite": DEMO_SATELLITE,
        "recording_id": recording_id,
        "mission_database": str(mission_path),
        "telemetry_database": str(telemetry_path),
        "recording": str(writer.data_path),
        "packets_processed": processed_packets,
        "packets_decoded": decoded_packets,
        "packets_failed": failed_packets,
        "replay": replay_status_dict,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orbitwatch-demo",
        description=(
            "Run the OrbitWatch controlled development replay."
        ),
    )

    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="OrbitWatch data directory.",
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier.",
    )

    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Preserve recorded event timing during replay.",
    )

    return parser


def main(
    argv: Iterable[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run_demo(
            data_root=args.data_root,
            speed=args.speed,
            realtime=args.realtime,
        )

    except Exception as exc:
        print()
        print("OrbitWatch Development Replay")
        print("==============================")
        print("STATUS: ERROR")
        print()
        print(str(exc))
        return 1

    print()
    print("OrbitWatch Development Replay")
    print("==============================")
    print("STATUS: COMPLETED")
    print("MODE:   REPLAY / DEVELOPMENT")
    print(f"Satellite:         {result['satellite']}")
    print(f"Recording:         {result['recording_id']}")
    print(f"Packets processed: {result['packets_processed']}")
    print(f"Packets decoded:   {result['packets_decoded']}")
    print(f"Packets failed:    {result['packets_failed']}")
    print()
    print(f"Telemetry DB: {result['telemetry_database']}")
    print(f"Mission DB:   {result['mission_database']}")
    print(f"Recording:    {result['recording']}")
    print()
    print("The data is controlled development/replay data.")
    print("No live RF transmission was performed.")
    print()

    return 0
