from __future__ import annotations

import uuid
from typing import Any

from .database import MissionLogDatabase
from .models import (
    MissionEvent,
    MissionEventSeverity,
    MissionEventType,
    utc_now,
)


class MissionLogger:
    """
    High-level operational logger for OrbitWatch.

    Every helper creates a structured MissionEvent and persists it immediately.
    """

    def __init__(
        self,
        database: MissionLogDatabase,
        *,
        mission_id: str | None = None,
    ) -> None:
        self.database = database
        self.mission_id = mission_id

    @staticmethod
    def _event_id() -> str:
        return f"evt-{uuid.uuid4().hex}"

    def log(
        self,
        event_type: MissionEventType | str,
        message: str,
        *,
        severity: MissionEventSeverity = MissionEventSeverity.INFO,
        satellite: str | None = None,
        recording_id: str | None = None,
        packet_id: str | None = None,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> MissionEvent:
        if isinstance(event_type, str):
            event_type = MissionEventType(event_type)

        event = MissionEvent(
            event_id=self._event_id(),
            timestamp=timestamp or utc_now(),
            event_type=event_type,
            severity=severity,
            message=message,
            mission_id=self.mission_id,
            satellite=satellite,
            recording_id=recording_id,
            packet_id=packet_id,
            payload=dict(payload or {}),
        )

        return self.database.insert_event(event)

    def mission_started(
        self,
        *,
        mode: str,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.MISSION_STARTED,
            f"Mission session started in {mode} mode.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            payload={
                "mode": mode,
                **(payload or {}),
            },
        )

    def mission_stopped(
        self,
        *,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.MISSION_STOPPED,
            "Mission session stopped.",
            severity=MissionEventSeverity.INFO,
            satellite=satellite,
            payload=payload,
        )

    def satellite_acquired(
        self,
        satellite: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SATELLITE_ACQUIRED,
            f"Satellite acquired: {satellite}.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            payload=payload,
        )

    def satellite_lost(
        self,
        satellite: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SATELLITE_LOST,
            f"Satellite signal/contact lost: {satellite}.",
            severity=MissionEventSeverity.WARNING,
            satellite=satellite,
            payload=payload,
        )

    def pass_started(
        self,
        satellite: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.PASS_STARTED,
            f"Satellite pass started: {satellite}.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            payload=payload,
        )

    def pass_ended(
        self,
        satellite: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.PASS_ENDED,
            f"Satellite pass ended: {satellite}.",
            severity=MissionEventSeverity.INFO,
            satellite=satellite,
            payload=payload,
        )

    def sdr_connected(
        self,
        *,
        device: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SDR_CONNECTED,
            "SDR receiver connected.",
            severity=MissionEventSeverity.SUCCESS,
            payload={
                "device": device,
                **(payload or {}),
            },
        )

    def sdr_disconnected(
        self,
        *,
        device: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SDR_DISCONNECTED,
            "SDR receiver disconnected.",
            severity=MissionEventSeverity.WARNING,
            payload={
                "device": device,
                **(payload or {}),
            },
        )

    def sdr_error(
        self,
        message: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SDR_ERROR,
            message,
            severity=MissionEventSeverity.ERROR,
            payload=payload,
        )

    def signal_detected(
        self,
        *,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SIGNAL_DETECTED,
            "RF signal detected.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            payload=payload,
        )

    def signal_lost(
        self,
        *,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SIGNAL_LOST,
            "RF signal lost.",
            severity=MissionEventSeverity.WARNING,
            satellite=satellite,
            payload=payload,
        )

    def packet_received(
        self,
        *,
        packet_id: str | None = None,
        satellite: str | None = None,
        protocol: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.PACKET_RECEIVED,
            "Packet received and accepted.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            packet_id=packet_id,
            payload={
                "protocol": protocol,
                **(payload or {}),
            },
        )

    def packet_rejected(
        self,
        message: str = "Packet rejected.",
        *,
        satellite: str | None = None,
        packet_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.PACKET_REJECTED,
            message,
            severity=MissionEventSeverity.WARNING,
            satellite=satellite,
            packet_id=packet_id,
            payload=payload,
        )

    def crc_error(
        self,
        *,
        satellite: str | None = None,
        packet_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.CRC_ERROR,
            "Packet CRC validation failed.",
            severity=MissionEventSeverity.ERROR,
            satellite=satellite,
            packet_id=packet_id,
            payload=payload,
        )

    def telemetry_received(
        self,
        *,
        satellite: str | None = None,
        packet_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.TELEMETRY_RECEIVED,
            "Telemetry decoded successfully.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            packet_id=packet_id,
            payload=payload,
        )

    def telemetry_decode_error(
        self,
        message: str,
        *,
        satellite: str | None = None,
        packet_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.TELEMETRY_DECODE_ERROR,
            message,
            severity=MissionEventSeverity.ERROR,
            satellite=satellite,
            packet_id=packet_id,
            payload=payload,
        )

    def recording_started(
        self,
        recording_id: str,
        *,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.RECORDING_STARTED,
            f"Recording started: {recording_id}.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            recording_id=recording_id,
            payload=payload,
        )

    def recording_stopped(
        self,
        recording_id: str,
        *,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.RECORDING_STOPPED,
            f"Recording stopped: {recording_id}.",
            severity=MissionEventSeverity.INFO,
            satellite=satellite,
            recording_id=recording_id,
            payload=payload,
        )

    def replay_started(
        self,
        recording_id: str,
        *,
        satellite: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.REPLAY_STARTED,
            f"Replay started: {recording_id}.",
            severity=MissionEventSeverity.SUCCESS,
            satellite=satellite,
            recording_id=recording_id,
            payload=payload,
        )

    def replay_paused(
        self,
        recording_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.REPLAY_PAUSED,
            f"Replay paused: {recording_id}.",
            severity=MissionEventSeverity.INFO,
            recording_id=recording_id,
            payload=payload,
        )

    def replay_resumed(
        self,
        recording_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.REPLAY_RESUMED,
            f"Replay resumed: {recording_id}.",
            severity=MissionEventSeverity.INFO,
            recording_id=recording_id,
            payload=payload,
        )

    def replay_stopped(
        self,
        recording_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.REPLAY_STOPPED,
            f"Replay stopped: {recording_id}.",
            severity=MissionEventSeverity.WARNING,
            recording_id=recording_id,
            payload=payload,
        )

    def replay_completed(
        self,
        recording_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.REPLAY_COMPLETED,
            f"Replay completed: {recording_id}.",
            severity=MissionEventSeverity.SUCCESS,
            recording_id=recording_id,
            payload=payload,
        )

    def warning(
        self,
        message: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SYSTEM_WARNING,
            message,
            severity=MissionEventSeverity.WARNING,
            payload=payload,
        )

    def error(
        self,
        message: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        return self.log(
            MissionEventType.SYSTEM_ERROR,
            message,
            severity=MissionEventSeverity.ERROR,
            payload=payload,
        )
