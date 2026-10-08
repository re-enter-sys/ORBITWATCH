"""
Persistent telemetry database for OrbitWatch.

SQLite is used so OrbitWatch can operate entirely on a Linux ground
station without requiring a separate database service.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .parser import TelemetryRecord


class TelemetryDatabase:
    """
    SQLite-backed telemetry history database.
    """

    def __init__(
        self,
        path: str | Path = "data/telemetry/orbitwatch.db",
    ) -> None:
        self.path = Path(path)

        if str(self.path) != ":memory:":
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self._connection: sqlite3.Connection | None = None

        self.connect()
        self.initialize()

    def connect(self) -> None:
        """Open the SQLite database connection."""

        if self._connection is not None:
            return

        database_path = str(self.path)

        self._connection = sqlite3.connect(
            database_path,
            check_same_thread=False,
        )

        self._connection.row_factory = sqlite3.Row

        self._connection.execute(
            "PRAGMA foreign_keys = ON"
        )

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the active database connection."""

        if self._connection is None:
            self.connect()

        assert self._connection is not None

        return self._connection

    def initialize(self) -> None:
        """Create database tables and indexes."""

        connection = self.connection

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telemetry_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                satellite TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                packet_id TEXT,
                valid INTEGER NOT NULL,
                crc_ok INTEGER,
                raw_payload TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                value_json TEXT,
                unit TEXT,
                data_type TEXT NOT NULL,
                raw_value TEXT,
                FOREIGN KEY(record_id)
                    REFERENCES telemetry_records(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_records_satellite
                ON telemetry_records(satellite);

            CREATE INDEX IF NOT EXISTS idx_telemetry_records_timestamp
                ON telemetry_records(timestamp);

            CREATE INDEX IF NOT EXISTS idx_telemetry_values_record
                ON telemetry_values(record_id);

            CREATE INDEX IF NOT EXISTS idx_telemetry_values_name
                ON telemetry_values(name);
            """
        )

        connection.commit()

    def insert(
        self,
        record: TelemetryRecord,
    ) -> int:
        """
        Store one telemetry record.

        Returns:
            Database ID of the inserted record.
        """

        if not isinstance(record, TelemetryRecord):
            raise TypeError(
                "record must be a TelemetryRecord."
            )

        connection = self.connection

        cursor = connection.execute(
            """
            INSERT INTO telemetry_records (
                satellite,
                timestamp,
                source,
                packet_id,
                valid,
                crc_ok,
                raw_payload,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.satellite,
                record.timestamp.isoformat(),
                record.source,
                record.packet_id,
                int(record.valid),
                (
                    None
                    if record.crc_ok is None
                    else int(record.crc_ok)
                ),
                self._serialize_raw_payload(
                    record.raw_payload
                ),
                json.dumps(
                    record.metadata,
                    default=str,
                    sort_keys=True,
                ),
                datetime.now(
                    record.timestamp.tzinfo
                ).isoformat(),
            ),
        )

        record_id = int(cursor.lastrowid)

        for name, value in record.values.items():
            connection.execute(
                """
                INSERT INTO telemetry_values (
                    record_id,
                    name,
                    value_json,
                    unit,
                    data_type,
                    raw_value
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    name,
                    json.dumps(
                        value.value,
                        default=str,
                    ),
                    value.unit,
                    value.data_type,
                    value.raw_value,
                ),
            )

        connection.commit()

        return record_id

    def insert_many(
        self,
        records: Iterable[TelemetryRecord],
    ) -> list[int]:
        """Insert multiple telemetry records."""

        ids = []

        for record in records:
            ids.append(self.insert(record))

        return ids

    def count(
        self,
        satellite: str | None = None,
    ) -> int:
        """Return the number of stored telemetry records."""

        if satellite is None:
            row = self.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM telemetry_records
                """
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM telemetry_records
                WHERE satellite = ?
                """,
                (satellite,),
            ).fetchone()

        return int(row["count"])

    def list_satellites(self) -> tuple[str, ...]:
        """Return satellites represented in the database."""

        rows = self.connection.execute(
            """
            SELECT DISTINCT satellite
            FROM telemetry_records
            ORDER BY satellite
            """
        ).fetchall()

        return tuple(
            str(row["satellite"])
            for row in rows
        )

    def latest(
        self,
        satellite: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the newest telemetry record."""

        if satellite is None:
            row = self.connection.execute(
                """
                SELECT *
                FROM telemetry_records
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT *
                FROM telemetry_records
                WHERE satellite = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (satellite,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record_dict(row)

    def history(
        self,
        satellite: str | None = None,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Return telemetry history ordered newest first.
        """

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        if satellite is None:
            rows = self.connection.execute(
                """
                SELECT *
                FROM telemetry_records
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT *
                FROM telemetry_records
                WHERE satellite = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (
                    satellite,
                    limit,
                ),
            ).fetchall()

        return [
            self._row_to_record_dict(row)
            for row in rows
        ]

    def find_by_packet_id(
        self,
        packet_id: str,
    ) -> dict[str, Any] | None:
        """Find telemetry using a packet ID."""

        row = self.connection.execute(
            """
            SELECT *
            FROM telemetry_records
            WHERE packet_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (packet_id,),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_record_dict(row)

    def delete_all(self) -> int:
        """Delete all telemetry records."""

        cursor = self.connection.execute(
            "DELETE FROM telemetry_records"
        )

        self.connection.commit()

        return cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""

        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "TelemetryDatabase":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

    @staticmethod
    def _serialize_raw_payload(
        payload: str | bytes | None,
    ) -> str | None:
        if payload is None:
            return None

        if isinstance(payload, bytes):
            return payload.decode(
                "utf-8",
                errors="replace",
            )

        return str(payload)

    def _row_to_record_dict(
        self,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        """Convert a database row into a dashboard-friendly record."""

        values_rows = self.connection.execute(
            """
            SELECT
                name,
                value_json,
                unit,
                data_type,
                raw_value
            FROM telemetry_values
            WHERE record_id = ?
            ORDER BY id
            """,
            (row["id"],),
        ).fetchall()

        values: dict[str, dict[str, Any]] = {}

        for value_row in values_rows:
            try:
                value = json.loads(
                    value_row["value_json"]
                )
            except (
                TypeError,
                json.JSONDecodeError,
            ):
                value = value_row["value_json"]

            values[value_row["name"]] = {
                "value": value,
                "unit": value_row["unit"],
                "data_type": value_row["data_type"],
                "raw_value": value_row["raw_value"],
            }

        try:
            metadata = json.loads(
                row["metadata_json"]
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            metadata = {}

        return {
            "id": row["id"],
            "satellite": row["satellite"],
            "timestamp": row["timestamp"],
            "source": row["source"],
            "packet_id": row["packet_id"],
            "valid": bool(row["valid"]),
            "crc_ok": (
                None
                if row["crc_ok"] is None
                else bool(row["crc_ok"])
            ),
            "raw_payload": row["raw_payload"],
            "metadata": metadata,
            "values": values,
        }
