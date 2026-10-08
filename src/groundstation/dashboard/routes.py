from __future__ import annotations

import json
import math
import sqlite3
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, render_template, request

from ..config import GroundStationConfig
from ..sdr.device import SDRDeviceManager
from ..sdr.receiver import SDRReceiver
from ..telemetry.database import TelemetryDatabase
from ..runtime import (
    OperatingMode,
    read_runtime_state,
    set_idle,
    set_replay,
)


dashboard_bp = Blueprint("dashboard", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_DATABASE = (
    PROJECT_ROOT
    / "data"
    / "telemetry"
    / "orbitwatch.db"
)

MISSION_DATABASE_CANDIDATES = (
    PROJECT_ROOT / "data" / "mission" / "mission.db",
    PROJECT_ROOT / "data" / "mission" / "orbitwatch.db",
    PROJECT_ROOT / "data" / "mission" / "orbitwatch-mission.db",
    PROJECT_ROOT / "data" / "mission" / "mission_log.db",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_number(value: Any) -> int | float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return value

    return None


def _normalize_timestamp(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    return value


def _normalize_dashboard_value(value: Any) -> Any:
    """
    Convert a telemetry value into JSON-safe dashboard data.

    The telemetry database currently reconstructs values as dictionaries,
    while the parser/engine may also expose value objects. Support both
    representations without changing the telemetry subsystem.
    """

    if isinstance(value, dict):
        result = dict(value)

        if "value" in result:
            result["value"] = _normalize_json_value(
                result.get("value")
            )

        if "unit" not in result:
            result["unit"] = None

        if "data_type" not in result:
            result["data_type"] = None

        if "raw_value" in result:
            result["raw_value"] = _normalize_json_value(
                result.get("raw_value")
            )

        return result

    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()

            if isinstance(converted, dict):
                return _normalize_dashboard_value(
                    converted
                )

        except Exception:
            pass

    if hasattr(value, "value"):
        return {
            "value": _normalize_json_value(
                getattr(value, "value", None)
            ),
            "unit": getattr(
                value,
                "unit",
                None,
            ),
            "data_type": getattr(
                value,
                "data_type",
                None,
            ),
        }

    return _normalize_json_value(value)


def _normalize_json_value(value: Any) -> Any:
    """
    Convert common Python values into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, str)):
        return value

    if isinstance(value, float):
        return (
            value
            if math.isfinite(value)
            else None
        )

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(key): _normalize_json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _normalize_json_value(item)
            for item in value
        ]

    return str(value)


def _record_to_dashboard(record: Any) -> dict[str, Any]:
    """
    Convert a telemetry database record into dashboard-safe JSON.

    TelemetryDatabase currently returns dictionaries from latest() and
    history(), while other parts of the application may provide objects
    implementing to_dict(). Support both forms without changing the
    telemetry subsystem.
    """
    if record is None:
        return {}

    # ------------------------------------------------------------------
    # Database-backed records are dictionaries.
    # ------------------------------------------------------------------
    if isinstance(record, dict):
        data = dict(record)

        raw_values = data.get("values") or {}
        normalized_values: dict[str, Any] = {}

        if isinstance(raw_values, dict):
            for name, value in raw_values.items():

                if isinstance(value, dict):
                    normalized_values[str(name)] = {
                        "value": value.get("value"),
                        "unit": value.get("unit"),
                        "data_type": value.get("data_type"),
                        "raw_value": value.get("raw_value"),
                    }

                elif hasattr(value, "to_dict"):
                    try:
                        converted = value.to_dict()

                        if isinstance(converted, dict):
                            normalized_values[str(name)] = converted
                            continue

                    except Exception:
                        pass

                    normalized_values[str(name)] = value

                elif hasattr(value, "value"):
                    normalized_values[str(name)] = {
                        "value": value.value,
                        "unit": getattr(
                            value,
                            "unit",
                            None,
                        ),
                        "data_type": getattr(
                            value,
                            "data_type",
                            None,
                        ),
                    }

                else:
                    normalized_values[str(name)] = value

        timestamp = data.get("timestamp")

        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()

        metadata = data.get("metadata") or {}

        if not isinstance(metadata, dict):
            metadata = {
                "value": metadata,
            }

        return {
            "id": data.get("id"),
            "satellite": data.get("satellite"),
            "timestamp": timestamp,
            "source": data.get(
                "source",
                "unknown",
            ),
            "packet_id": data.get("packet_id"),
            "valid": bool(
                data.get(
                    "valid",
                    True,
                )
            ),
            "crc_ok": data.get("crc_ok"),
            "raw_payload": data.get("raw_payload"),
            "values": normalized_values,
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Object-backed telemetry records.
    # ------------------------------------------------------------------
    if hasattr(record, "to_dict"):
        try:
            data = record.to_dict()

            if isinstance(data, dict):
                return _record_to_dashboard(data)

        except Exception:
            pass

    values: dict[str, Any] = {}

    raw_values = getattr(
        record,
        "values",
        {},
    ) or {}

    if isinstance(raw_values, dict):
        for name, value in raw_values.items():

            if hasattr(value, "to_dict"):
                try:
                    converted = value.to_dict()

                    if isinstance(converted, dict):
                        values[str(name)] = converted
                        continue

                except Exception:
                    pass

            if hasattr(value, "value"):
                values[str(name)] = {
                    "value": value.value,
                    "unit": getattr(
                        value,
                        "unit",
                        None,
                    ),
                    "data_type": getattr(
                        value,
                        "data_type",
                        None,
                    ),
                }

            else:
                values[str(name)] = value

    timestamp = getattr(
        record,
        "timestamp",
        None,
    )

    if hasattr(timestamp, "isoformat"):
        timestamp = timestamp.isoformat()

    metadata = getattr(
        record,
        "metadata",
        {},
    ) or {}

    if not isinstance(metadata, dict):
        metadata = {
            "value": metadata,
        }

    return {
        "id": getattr(
            record,
            "id",
            None,
        ),
        "satellite": getattr(
            record,
            "satellite",
            None,
        ),
        "timestamp": timestamp,
        "source": getattr(
            record,
            "source",
            "unknown",
        ),
        "packet_id": getattr(
            record,
            "packet_id",
            None,
        ),
        "valid": bool(
            getattr(
                record,
                "valid",
                True,
            )
        ),
        "crc_ok": getattr(
            record,
            "crc_ok",
            None,
        ),
        "raw_payload": getattr(
            record,
            "raw_payload",
            None,
        ),
        "values": values,
        "metadata": metadata,
    }


def _database() -> TelemetryDatabase:
    DEFAULT_DATABASE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return TelemetryDatabase(
        str(DEFAULT_DATABASE)
    )


def _read_database_statistics() -> dict[str, Any]:
    try:
        db = _database()

        try:
            total = db.count()
            satellites = db.list_satellites()
            latest = db.latest()

            dashboard_latest = (
                _record_to_dashboard(latest)
                if latest
                else None
            )

            return {
                "records": int(total),
                "satellites": list(satellites),
                "latest": dashboard_latest,
            }

        finally:
            db.close()

    except Exception as exc:
        return {
            "records": 0,
            "satellites": [],
            "latest": None,
            "error": str(exc),
        }


def _read_history(
    limit: int = 50,
) -> list[dict[str, Any]]:

    try:
        db = _database()

        try:
            records = db.history(
                limit=max(
                    1,
                    min(
                        int(limit),
                        500,
                    ),
                )
            )

            return [
                _record_to_dashboard(record)
                for record in records
            ]

        finally:
            db.close()

    except Exception:
        return []


def _read_sdr_status() -> dict[str, Any]:
    """Return SDR state without requiring physical SDR hardware."""

    try:
        receiver = SDRReceiver()

        status = receiver.status()

        if hasattr(status, "to_dict"):
            result = status.to_dict()

        elif isinstance(status, dict):
            result = dict(status)

        else:
            result = {
                "state": getattr(
                    status,
                    "state",
                    "IDLE",
                ),
            }

        result.setdefault(
            "available",
            False,
        )

        result.setdefault(
            "state",
            "IDLE",
        )

        return result

    except Exception as exc:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "error": str(exc),
        }


def _read_sdr_devices() -> list[dict[str, Any]]:
    try:
        manager = SDRDeviceManager()

        devices = manager.discover()

        result: list[dict[str, Any]] = []

        for device in devices:
            result.append(
                {
                    "index": getattr(
                        device,
                        "index",
                        None,
                    ),
                    "name": getattr(
                        device,
                        "name",
                        "Unknown SDR",
                    ),
                    "driver": getattr(
                        device,
                        "driver",
                        None,
                    ),
                    "serial": getattr(
                        device,
                        "serial",
                        None,
                    ),
                    "state": str(
                        getattr(
                            device,
                            "state",
                            "UNKNOWN",
                        )
                    ),
                    "identifier": getattr(
                        device,
                        "identifier",
                        getattr(
                            device,
                            "name",
                            "Unknown SDR",
                        ),
                    ),
                }
            )

        return result

    except Exception:
        return []


def _read_config() -> dict[str, Any]:
    try:
        config = GroundStationConfig()

        data: dict[str, Any] = {}

        for name in (
            "name",
            "station_name",
            "latitude",
            "longitude",
            "altitude_m",
        ):
            if hasattr(config, name):
                value = getattr(
                    config,
                    name,
                )

                if not callable(value):
                    data[name] = value

        return data

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Mission Log
# ---------------------------------------------------------------------------

def _mission_database_path() -> Path | None:
    """
    Locate the Mission Log database without assuming one hard-coded filename.

    The Mission Log subsystem is allowed to evolve its filename while the
    dashboard remains compatible with the existing project layout.
    """

    for candidate in MISSION_DATABASE_CANDIDATES:
        if candidate.exists():
            return candidate

    mission_dir = PROJECT_ROOT / "data" / "mission"

    if mission_dir.exists():
        databases = sorted(
            mission_dir.glob("*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        if databases:
            return databases[0]

    return None


def _mission_schema(
    connection: sqlite3.Connection,
) -> set[str]:

    try:
        rows = connection.execute(
            "PRAGMA table_info(mission_events)"
        ).fetchall()

        return {
            str(row[1])
            for row in rows
        }

    except sqlite3.Error:
        return set()


def _mission_value(
    row: sqlite3.Row,
    columns: set[str],
    name: str,
    default: Any = None,
) -> Any:

    if name not in columns:
        return default

    try:
        return row[name]
    except Exception:
        return default


def _decode_payload(
    value: Any,
) -> dict[str, Any]:

    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)

            if isinstance(parsed, dict):
                return parsed

            return {
                "value": parsed,
            }

        except Exception:
            return {
                "raw": value,
            }

    return {
        "value": value,
    }


def _mission_event_from_row(
    row: sqlite3.Row,
    columns: set[str],
) -> dict[str, Any]:

    event_type = _mission_value(
        row,
        columns,
        "event_type",
        "CUSTOM",
    )

    severity = _mission_value(
        row,
        columns,
        "severity",
        "INFO",
    )

    payload = _decode_payload(
        _mission_value(
            row,
            columns,
            "payload",
            None,
        )
    )

    return {
        "id": _mission_value(
            row,
            columns,
            "id",
            None,
        ),
        "mission_id": _mission_value(
            row,
            columns,
            "mission_id",
            None,
        ),
        "timestamp": _mission_value(
            row,
            columns,
            "timestamp",
            None,
        ),
        "event_type": str(
            event_type or "CUSTOM"
        ),
        "severity": str(
            severity or "INFO"
        ),
        "message": _mission_value(
            row,
            columns,
            "message",
            "",
        ),
        "satellite": _mission_value(
            row,
            columns,
            "satellite",
            None,
        ),
        "packet_id": _mission_value(
            row,
            columns,
            "packet_id",
            None,
        ),
        "recording_id": _mission_value(
            row,
            columns,
            "recording_id",
            None,
        ),
        "payload": payload,
    }


def _read_mission_events(
    *,
    limit: int = 100,
    offset: int = 0,
    mission_id: str | None = None,
    satellite: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:

    path = _mission_database_path()

    if path is None:
        return {
            "available": False,
            "database": None,
            "events": [],
            "total": 0,
            "statistics": {
                "events": 0,
                "missions": 0,
                "satellites": 0,
                "errors": 0,
                "warnings": 0,
            },
        }

    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(
            str(path)
        )

        connection.row_factory = sqlite3.Row

        columns = _mission_schema(
            connection
        )

        if not columns:
            return {
                "available": False,
                "database": str(path),
                "events": [],
                "total": 0,
                "statistics": {
                    "events": 0,
                    "missions": 0,
                    "satellites": 0,
                    "errors": 0,
                    "warnings": 0,
                },
            }

        conditions: list[str] = []
        parameters: list[Any] = []

        if mission_id and "mission_id" in columns:
            conditions.append(
                "mission_id = ?"
            )
            parameters.append(
                mission_id
            )

        if satellite and "satellite" in columns:
            conditions.append(
                "satellite = ?"
            )
            parameters.append(
                satellite
            )

        if event_type and "event_type" in columns:
            conditions.append(
                "event_type = ?"
            )
            parameters.append(
                event_type
            )

        if severity and "severity" in columns:
            conditions.append(
                "severity = ?"
            )
            parameters.append(
                severity
            )

        if search:
            search_value = f"%{search.lower()}%"

            search_columns = [
                column
                for column in (
                    "message",
                    "event_type",
                    "satellite",
                    "packet_id",
                    "recording_id",
                    "payload",
                )
                if column in columns
            ]

            if search_columns:
                conditions.append(
                    "("
                    + " OR ".join(
                        f"LOWER(CAST({column} AS TEXT)) LIKE ?"
                        for column in search_columns
                    )
                    + ")"
                )

                parameters.extend(
                    [search_value]
                    * len(search_columns)
                )

        where = ""

        if conditions:
            where = (
                " WHERE "
                + " AND ".join(conditions)
            )

        order_column = (
            "timestamp"
            if "timestamp" in columns
            else "id"
        )

        count_row = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM mission_events
            {where}
            """,
            parameters,
        ).fetchone()

        total = int(
            count_row[0]
            if count_row
            else 0
        )

        safe_limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

        safe_offset = max(
            0,
            int(offset),
        )

        rows = connection.execute(
            f"""
            SELECT *
            FROM mission_events
            {where}
            ORDER BY {order_column} DESC
            LIMIT ? OFFSET ?
            """,
            [
                *parameters,
                safe_limit,
                safe_offset,
            ],
        ).fetchall()

        events = [
            _mission_event_from_row(
                row,
                columns,
            )
            for row in rows
        ]

        stats_rows = connection.execute(
            """
            SELECT
                COUNT(*) AS events,
                COUNT(
                    DISTINCT mission_id
                ) AS missions,
                COUNT(
                    DISTINCT satellite
                ) AS satellites,
                SUM(
                    CASE
                        WHEN severity = 'ERROR'
                        THEN 1
                        ELSE 0
                    END
                ) AS errors,
                SUM(
                    CASE
                        WHEN severity = 'WARNING'
                        THEN 1
                        ELSE 0
                    END
                ) AS warnings
            FROM mission_events
            """
        ).fetchone()

        statistics = {
            "events": int(
                stats_rows["events"] or 0
            ),
            "missions": int(
                stats_rows["missions"] or 0
            ),
            "satellites": int(
                stats_rows["satellites"] or 0
            ),
            "errors": int(
                stats_rows["errors"] or 0
            ),
            "warnings": int(
                stats_rows["warnings"] or 0
            ),
        }

        return {
            "available": True,
            "database": str(path),
            "events": events,
            "total": total,
            "statistics": statistics,
        }

    except Exception as exc:
        return {
            "available": False,
            "database": str(path),
            "events": [],
            "total": 0,
            "statistics": {
                "events": 0,
                "missions": 0,
                "satellites": 0,
                "errors": 0,
                "warnings": 0,
            },
            "error": str(exc),
        }

    finally:
        if connection is not None:
            connection.close()


def _mission_event_types() -> list[str]:
    data = _read_mission_events(
        limit=500
    )

    values = sorted(
        {
            str(
                event.get(
                    "event_type",
                    "CUSTOM",
                )
            )
            for event in data.get(
                "events",
                [],
            )
        }
    )

    return values


# ---------------------------------------------------------------------------
# Dashboard routes
# ---------------------------------------------------------------------------

@dashboard_bp.get("/")
def index():
    return render_template(
        "index.html"
    )


@dashboard_bp.get("/api/status")
def api_status():

    database = _read_database_statistics()
    sdr = _read_sdr_status()
    mission = _read_mission_events(
        limit=1
    )

    runtime = read_runtime_state()

    return jsonify(
        {
            "application": "OrbitWatch",
            "version": "0.1.0",
            "status": "online",
            "timestamp": _utc_now(),

            # Current operating mode comes from shared runtime
            # state, never from historical telemetry records.
            "mode": runtime.mode,

            "interaction_mode": "ACTIVE",

            "runtime": runtime.to_dict(),

            "sdr": sdr,

            "database": {
                "records": database["records"],
                "satellites": database[
                    "satellites"
                ],
            },

            "mission_log": {
                "available": mission[
                    "available"
                ],
                "events": mission[
                    "statistics"
                ]["events"],
            },
        }
    )


@dashboard_bp.get("/api/overview")
def api_overview():

    database = _read_database_statistics()

    latest = database["latest"]

    telemetry_values = []

    if latest:
        values = latest.get(
            "values",
            {},
        )

        if isinstance(values, dict):
            for name, value in values.items():

                normalized = (
                    _normalize_dashboard_value(
                        value
                    )
                )

                if isinstance(
                    normalized,
                    dict,
                ):
                    telemetry_values.append(
                        {
                            "name": name,
                            "value": normalized.get(
                                "value"
                            ),
                            "unit": normalized.get(
                                "unit"
                            ),
                            "data_type": normalized.get(
                                "data_type"
                            ),
                        }
                    )

                else:
                    telemetry_values.append(
                        {
                            "name": name,
                            "value": normalized,
                            "unit": None,
                            "data_type": None,
                        }
                    )

    return jsonify(
        {
            "application": "OrbitWatch",
            "status": "online",
            "timestamp": _utc_now(),

            "satellite": (
                latest.get(
                    "satellite"
                )
                if latest
                else None
            ),

            "last_packet": latest,

            "telemetry": telemetry_values,

            "statistics": {
                "packet_count": database[
                    "records"
                ],
                "satellite_count": len(
                    database[
                        "satellites"
                    ]
                ),
            },

            "data_available": (
                latest is not None
            ),

            # Current mode is runtime state. Historical telemetry
            # does not change the operating mode.
            "mode": read_runtime_state().mode,

            "runtime": read_runtime_state().to_dict(),

            "data_source": (
                latest.get(
                    "source",
                    "unknown",
                )
                if latest
                else None
            ),

            "development_data": bool(
                latest
                and (
                    str(
                        latest.get(
                            "source",
                            ""
                        )
                    ).lower()
                    == "replay"
                    or str(
                        latest.get(
                            "metadata",
                            {}
                        ).get(
                            "mode",
                            ""
                        )
                    ).upper()
                    == "REPLAY"
                )
            ),
        }
    )


@dashboard_bp.get("/api/telemetry")
def api_telemetry():

    database = _read_database_statistics()

    return jsonify(
        {
            "latest": database["latest"],
            "satellites": database[
                "satellites"
            ],
            "count": database[
                "records"
            ],
            "timestamp": _utc_now(),
        }
    )


@dashboard_bp.get("/api/telemetry/history")
def api_telemetry_history():

    requested_limit = request.args.get(
        "limit",
        "50",
    )

    try:
        limit = int(
            requested_limit
        )
    except ValueError:
        limit = 50

    return jsonify(
        {
            "history": _read_history(
                limit=limit
            ),
            "timestamp": _utc_now(),
        }
    )


@dashboard_bp.get("/api/sdr")
def api_sdr():

    return jsonify(
        {
            "receiver": _read_sdr_status(),
            "devices": _read_sdr_devices(),
            "timestamp": _utc_now(),
        }
    )


@dashboard_bp.get("/api/mission")
def api_mission():

    database = _read_database_statistics()

    latest = database["latest"]

    active_satellite = (
        latest.get("satellite")
        if latest
        else None
    )

    last_contact = (
        latest.get("timestamp")
        if latest
        else None
    )

    replay_data = bool(
        latest
        and (
            str(
                latest.get(
                    "source",
                    "",
                )
            ).lower()
            == "replay"
            or str(
                latest.get(
                    "metadata",
                    {},
                ).get(
                    "mode",
                    "",
                )
            ).upper()
            == "REPLAY"
        )
    )

    return jsonify(
        {
            "station": _read_config(),

            "satellites": database[
                "satellites"
            ],

            # This is the satellite represented by the latest
            # persisted telemetry record. It is not presented as
            # proof of an active RF contact.
            "active_satellite": active_satellite,

            "packet_count": database[
                "records"
            ],

            "last_contact": last_contact,

            "mode": (
                "REPLAY"
                if replay_data
                else (
                    "TELEMETRY"
                    if latest
                    else "STANDBY"
                )
            ),

            "data_source": (
                latest.get(
                    "source",
                    "unknown",
                )
                if latest
                else None
            ),

            "development_data": replay_data,

            "rf_transmit": False,

            "timestamp": _utc_now(),
        }
    )


@dashboard_bp.get("/api/mission-log")
def api_mission_log():

    try:
        limit = int(
            request.args.get(
                "limit",
                "100",
            )
        )

    except ValueError:
        limit = 100

    try:
        offset = int(
            request.args.get(
                "offset",
                "0",
            )
        )

    except ValueError:
        offset = 0

    return jsonify(
        _read_mission_events(
            limit=limit,
            offset=offset,
            mission_id=request.args.get(
                "mission_id"
            ),
            satellite=request.args.get(
                "satellite"
            ),
            event_type=request.args.get(
                "event_type"
            ),
            severity=request.args.get(
                "severity"
            ),
            search=request.args.get(
                "search"
            ),
        )
    )


@dashboard_bp.get("/api/mission-log/types")
def api_mission_log_types():

    return jsonify(
        {
            "types": _mission_event_types(),
            "timestamp": _utc_now(),
        }
    )


@dashboard_bp.get("/api/health")
def api_health():

    database_ok = True

    try:
        db = _database()

        try:
            db.count()

        finally:
            db.close()

    except Exception:
        database_ok = False

    mission = _read_mission_events(
        limit=1
    )

    mission_ok = bool(
        mission.get(
            "available",
            False,
        )
    )

    return jsonify(
        {
            "status": (
                "ok"
                if database_ok
                else "degraded"
            ),
            "database": database_ok,
            "mission_log": mission_ok,
            "timestamp": _utc_now(),
        }
    )


# ---------------------------------------------------------------------------
# Operating mode control
# ---------------------------------------------------------------------------

_REPLAY_PROCESS: subprocess.Popen[bytes] | None = None


def _replay_process_running() -> bool:
    """Return whether the dashboard-started replay is still running."""

    global _REPLAY_PROCESS

    if _REPLAY_PROCESS is None:
        return False

    return_code = _REPLAY_PROCESS.poll()

    if return_code is None:
        return True

    _REPLAY_PROCESS = None
    return False


@dashboard_bp.get("/api/mode")
def api_mode():
    """Return the current OrbitWatch operating mode."""

    runtime = read_runtime_state()

    return jsonify(
        {
            "mode": runtime.mode,
            "runtime": runtime.to_dict(),
            "timestamp": _utc_now(),
        }
    )


@dashboard_bp.post("/api/mode")
def api_set_mode():
    """
    Change the OrbitWatch operating mode.

    IDLE can be selected directly.

    REPLAY starts the controlled development replay as a separate
    process. The replay process owns the runtime state and returns
    it to IDLE when the replay finishes.

    LIVE RF is deliberately not started by the dashboard. LIVE must
    come from a real receive-side SDR/input pipeline.
    """

    global _REPLAY_PROCESS

    payload = request.get_json(silent=True) or {}

    requested = str(
        payload.get("mode", "")
    ).upper().strip()

    if requested == OperatingMode.IDLE.value:
        if _replay_process_running():
            try:
                _REPLAY_PROCESS.terminate()
                _REPLAY_PROCESS.wait(timeout=3)
            except Exception:
                try:
                    _REPLAY_PROCESS.kill()
                except Exception:
                    pass
            finally:
                _REPLAY_PROCESS = None

        state = set_idle()

        return jsonify(
            {
                "success": True,
                "mode": state.mode,
                "runtime": state.to_dict(),
                "timestamp": _utc_now(),
            }
        )

    if requested == OperatingMode.REPLAY.value:

        if _replay_process_running():
            runtime = read_runtime_state()

            return jsonify(
                {
                    "success": True,
                    "mode": runtime.mode,
                    "runtime": runtime.to_dict(),
                    "already_running": True,
                    "timestamp": _utc_now(),
                }
            )

        project_root = PROJECT_ROOT

        environment = os.environ.copy()

        src_path = str(
            project_root / "src"
        )

        existing_pythonpath = environment.get(
            "PYTHONPATH",
            "",
        )

        environment["PYTHONPATH"] = (
            src_path
            if not existing_pythonpath
            else (
                src_path
                + os.pathsep
                + existing_pythonpath
            )
        )

        try:
            # The runtime helper owns the data_source value.
            # set_replay() intentionally accepts only session_id
            # and satellite.
            state = set_replay(
                satellite="OW-DEMO",
            )

            _REPLAY_PROCESS = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "src.main",
                    "demo",
                ],
                cwd=str(project_root),
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        except Exception as exc:
            _REPLAY_PROCESS = None

            state = set_idle()

            return (
                jsonify(
                    {
                        "success": False,
                        "mode": state.mode,
                        "runtime": state.to_dict(),
                        "error": (
                            "Unable to start the development "
                            f"replay: {exc}"
                        ),
                        "timestamp": _utc_now(),
                    }
                ),
                500,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "mode": state.mode,
                    "runtime": state.to_dict(),
                    "starting": True,
                    "timestamp": _utc_now(),
                }
            ),
            202,
        )

    if requested == OperatingMode.LIVE.value:
        runtime = read_runtime_state()

        return (
            jsonify(
                {
                    "success": False,
                    "mode": runtime.mode,
                    "runtime": runtime.to_dict(),
                    "error": (
                        "LIVE RF mode requires an actual SDR "
                        "receive pipeline. The dashboard will "
                        "not simulate LIVE RF."
                    ),
                    "timestamp": _utc_now(),
                }
            ),
            409,
        )

    runtime = read_runtime_state()

    return (
        jsonify(
            {
                "success": False,
                "mode": runtime.mode,
                "runtime": runtime.to_dict(),
                "error": f"Unsupported operating mode: {requested}",
                "timestamp": _utc_now(),
            }
        ),
        400,
    )
