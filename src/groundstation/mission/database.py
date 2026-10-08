from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import (
    MissionEvent,
    MissionEventSeverity,
    MissionEventType,
    MissionSession,
    MissionStatistics,
)


class MissionLogDatabase:
    """
    SQLite-backed mission history.

    Mission events are stored independently from telemetry so operational
    history remains available even when a packet does not contain telemetry.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

        if self.path.parent:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )
        self.connection.row_factory = sqlite3.Row

        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS mission_sessions (
                mission_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                satellite TEXT,
                mode TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS mission_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                mission_id TEXT,
                satellite TEXT,
                recording_id TEXT,
                packet_id TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_mission_events_timestamp
                ON mission_events(timestamp);

            CREATE INDEX IF NOT EXISTS idx_mission_events_type
                ON mission_events(event_type);

            CREATE INDEX IF NOT EXISTS idx_mission_events_severity
                ON mission_events(severity);

            CREATE INDEX IF NOT EXISTS idx_mission_events_mission
                ON mission_events(mission_id);

            CREATE INDEX IF NOT EXISTS idx_mission_events_satellite
                ON mission_events(satellite);

            CREATE INDEX IF NOT EXISTS idx_mission_events_packet
                ON mission_events(packet_id);
            """
        )

        self.connection.commit()

    def create_session(self, session: MissionSession) -> MissionSession:
        self.connection.execute(
            """
            INSERT INTO mission_sessions (
                mission_id,
                started_at,
                ended_at,
                satellite,
                mode,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.mission_id,
                session.started_at,
                session.ended_at,
                session.satellite,
                session.mode,
                json.dumps(session.metadata),
            ),
        )

        self.connection.commit()
        return session

    def close_session(
        self,
        mission_id: str,
        ended_at: str,
    ) -> MissionSession:
        self.connection.execute(
            """
            UPDATE mission_sessions
            SET ended_at = ?
            WHERE mission_id = ?
            """,
            (ended_at, mission_id),
        )

        self.connection.commit()

        session = self.get_session(mission_id)

        if session is None:
            raise KeyError(f"Mission session not found: {mission_id}")

        return session

    def get_session(self, mission_id: str) -> MissionSession | None:
        row = self.connection.execute(
            """
            SELECT
                s.*,
                (
                    SELECT COUNT(*)
                    FROM mission_events e
                    WHERE e.mission_id = s.mission_id
                ) AS event_count,
                (
                    SELECT COUNT(*)
                    FROM mission_events e
                    WHERE e.mission_id = s.mission_id
                    AND e.event_type = 'packet_received'
                ) AS packet_count,
                (
                    SELECT COUNT(*)
                    FROM mission_events e
                    WHERE e.mission_id = s.mission_id
                    AND e.event_type = 'telemetry_received'
                ) AS telemetry_count,
                (
                    SELECT COUNT(*)
                    FROM mission_events e
                    WHERE e.mission_id = s.mission_id
                    AND e.severity = 'error'
                ) AS error_count
            FROM mission_sessions s
            WHERE s.mission_id = ?
            """,
            (mission_id,),
        ).fetchone()

        if row is None:
            return None

        return MissionSession(
            mission_id=row["mission_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            satellite=row["satellite"],
            mode=row["mode"],
            event_count=row["event_count"],
            packet_count=row["packet_count"],
            telemetry_count=row["telemetry_count"],
            error_count=row["error_count"],
            metadata=json.loads(row["metadata_json"]),
        )

    def insert_event(self, event: MissionEvent) -> MissionEvent:
        self.connection.execute(
            """
            INSERT INTO mission_events (
                event_id,
                timestamp,
                event_type,
                severity,
                message,
                mission_id,
                satellite,
                recording_id,
                packet_id,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.timestamp,
                event.event_type.value,
                event.severity.value,
                event.message,
                event.mission_id,
                event.satellite,
                event.recording_id,
                event.packet_id,
                json.dumps(event.payload),
            ),
        )

        self.connection.commit()
        return event

    def insert_events(
        self,
        events: Iterable[MissionEvent],
    ) -> int:
        rows = [
            (
                event.event_id,
                event.timestamp,
                event.event_type.value,
                event.severity.value,
                event.message,
                event.mission_id,
                event.satellite,
                event.recording_id,
                event.packet_id,
                json.dumps(event.payload),
            )
            for event in events
        ]

        if not rows:
            return 0

        self.connection.executemany(
            """
            INSERT INTO mission_events (
                event_id,
                timestamp,
                event_type,
                severity,
                message,
                mission_id,
                satellite,
                recording_id,
                packet_id,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        self.connection.commit()

        return len(rows)

    def _row_to_event(self, row: sqlite3.Row) -> MissionEvent:
        return MissionEvent(
            event_id=row["event_id"],
            timestamp=row["timestamp"],
            event_type=MissionEventType(row["event_type"]),
            severity=MissionEventSeverity(row["severity"]),
            message=row["message"],
            mission_id=row["mission_id"],
            satellite=row["satellite"],
            recording_id=row["recording_id"],
            packet_id=row["packet_id"],
            payload=json.loads(row["payload_json"]),
        )

    def list_events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        mission_id: str | None = None,
        satellite: str | None = None,
        event_type: MissionEventType | str | None = None,
        severity: MissionEventSeverity | str | None = None,
    ) -> list[MissionEvent]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero.")

        if offset < 0:
            raise ValueError("offset cannot be negative.")

        query = """
            SELECT *
            FROM mission_events
            WHERE 1 = 1
        """

        parameters: list[Any] = []

        if mission_id is not None:
            query += " AND mission_id = ?"
            parameters.append(mission_id)

        if satellite is not None:
            query += " AND satellite = ?"
            parameters.append(satellite)

        if event_type is not None:
            value = (
                event_type.value
                if isinstance(event_type, MissionEventType)
                else str(event_type)
            )
            query += " AND event_type = ?"
            parameters.append(value)

        if severity is not None:
            value = (
                severity.value
                if isinstance(severity, MissionEventSeverity)
                else str(severity)
            )
            query += " AND severity = ?"
            parameters.append(value)

        query += """
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """

        parameters.extend([limit, offset])

        rows = self.connection.execute(
            query,
            parameters,
        ).fetchall()

        return [self._row_to_event(row) for row in rows]

    def search(
        self,
        text: str,
        *,
        limit: int = 100,
    ) -> list[MissionEvent]:
        if not text.strip():
            return self.list_events(limit=limit)

        pattern = f"%{text.strip()}%"

        rows = self.connection.execute(
            """
            SELECT *
            FROM mission_events
            WHERE
                message LIKE ?
                OR event_type LIKE ?
                OR satellite LIKE ?
                OR packet_id LIKE ?
                OR recording_id LIKE ?
                OR payload_json LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                limit,
            ),
        ).fetchall()

        return [self._row_to_event(row) for row in rows]

    def count(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM mission_events"
        ).fetchone()

        return int(row["count"])

    def statistics(self) -> MissionStatistics:
        total = self.count()

        severity_rows = self.connection.execute(
            """
            SELECT severity, COUNT(*) AS count
            FROM mission_events
            GROUP BY severity
            """
        ).fetchall()

        severity_counts = {
            row["severity"]: int(row["count"])
            for row in severity_rows
        }

        type_rows = self.connection.execute(
            """
            SELECT event_type, COUNT(*) AS count
            FROM mission_events
            GROUP BY event_type
            """
        ).fetchall()

        type_counts = {
            row["event_type"]: int(row["count"])
            for row in type_rows
        }

        return MissionStatistics(
            total_events=total,
            information_events=severity_counts.get("info", 0),
            success_events=severity_counts.get("success", 0),
            warning_events=severity_counts.get("warning", 0),
            error_events=severity_counts.get("error", 0),
            packet_events=type_counts.get("packet_received", 0),
            telemetry_events=type_counts.get("telemetry_received", 0),
            crc_errors=type_counts.get("crc_error", 0),
            recordings_started=type_counts.get("recording_started", 0),
            replays_completed=type_counts.get("replay_completed", 0),
        )

    def clear_events(self) -> None:
        self.connection.execute("DELETE FROM mission_events")
        self.connection.commit()

    def clear_sessions(self) -> None:
        self.connection.execute("DELETE FROM mission_sessions")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "MissionLogDatabase":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
