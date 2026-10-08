from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .database import MissionLogDatabase
from .logger import MissionLogger
from .models import (
    MissionEvent,
    MissionEventSeverity,
    MissionEventType,
    MissionSession,
    MissionStatistics,
    utc_now,
)


class MissionLogService:
    """
    Application-level Mission Log service.

    Handles mission sessions, structured events, searching and statistics.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database = MissionLogDatabase(database_path)
        self._logger: MissionLogger | None = None
        self._session: MissionSession | None = None

    @staticmethod
    def generate_mission_id() -> str:
        return f"mission-{uuid.uuid4().hex[:12]}"

    @property
    def session(self) -> MissionSession | None:
        return self._session

    @property
    def logger(self) -> MissionLogger:
        if self._logger is None:
            raise RuntimeError(
                "No active mission session."
            )

        return self._logger

    def start_mission(
        self,
        *,
        mode: str,
        satellite: str | None = None,
        mission_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MissionSession:
        if self._session is not None and self._session.active:
            raise RuntimeError("A mission session is already active.")

        mission_id = mission_id or self.generate_mission_id()

        session = MissionSession(
            mission_id=mission_id,
            started_at=utc_now(),
            satellite=satellite,
            mode=mode,
            metadata=dict(metadata or {}),
        )

        self.database.create_session(session)

        self._session = session
        self._logger = MissionLogger(
            self.database,
            mission_id=mission_id,
        )

        self._logger.mission_started(
            mode=mode,
            satellite=satellite,
            payload=metadata,
        )

        return self.database.get_session(mission_id) or session

    def stop_mission(
        self,
        *,
        satellite: str | None = None,
    ) -> MissionSession:
        if self._session is None:
            raise RuntimeError("No active mission session.")

        if not self._session.active:
            return self._session

        self.logger.mission_stopped(
            satellite=satellite or self._session.satellite,
        )

        stopped = self.database.close_session(
            self._session.mission_id,
            utc_now(),
        )

        self._session = stopped
        return stopped

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
    ) -> MissionEvent:
        return self.logger.log(
            event_type,
            message,
            severity=severity,
            satellite=satellite,
            recording_id=recording_id,
            packet_id=packet_id,
            payload=payload,
        )

    def events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        mission_id: str | None = None,
        satellite: str | None = None,
        event_type: MissionEventType | str | None = None,
        severity: MissionEventSeverity | str | None = None,
    ) -> list[MissionEvent]:
        return self.database.list_events(
            limit=limit,
            offset=offset,
            mission_id=mission_id,
            satellite=satellite,
            event_type=event_type,
            severity=severity,
        )

    def search(
        self,
        text: str,
        *,
        limit: int = 100,
    ) -> list[MissionEvent]:
        return self.database.search(
            text,
            limit=limit,
        )

    def statistics(self) -> MissionStatistics:
        return self.database.statistics()

    def status(self) -> dict[str, Any]:
        statistics = self.statistics()

        session = (
            self._session.to_dict()
            if self._session is not None
            else None
        )

        return {
            "active": (
                self._session is not None
                and self._session.active
            ),
            "session": session,
            "statistics": statistics.to_dict(),
        }

    def clear(self) -> None:
        self.database.clear_events()
        self.database.clear_sessions()

        self._session = None
        self._logger = None

    def close(self) -> None:
        self.database.close()

    def __enter__(self) -> "MissionLogService":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
