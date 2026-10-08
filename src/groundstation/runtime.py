from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class OperatingMode(str, Enum):
    """Current OrbitWatch operating mode."""

    IDLE = "IDLE"
    REPLAY = "REPLAY"
    LIVE = "LIVE"


@dataclass
class RuntimeState:
    """Shared runtime state for OrbitWatch processes."""

    mode: str = OperatingMode.IDLE.value
    session_id: str | None = None
    satellite: str | None = None
    data_source: str = "NONE"
    started_at: str | None = None
    updated_at: str | None = None
    status: str = "idle"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUNTIME_DIRECTORY = PROJECT_ROOT / "data" / "runtime"
STATE_FILE = RUNTIME_DIRECTORY / "state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_mode(mode: OperatingMode | str) -> str:
    if isinstance(mode, OperatingMode):
        return mode.value

    value = str(mode).upper().strip()

    if value in {
        OperatingMode.IDLE.value,
        OperatingMode.REPLAY.value,
        OperatingMode.LIVE.value,
    }:
        return value

    raise ValueError(f"Unsupported operating mode: {mode}")


def _default_state() -> RuntimeState:
    now = _utc_now()

    return RuntimeState(
        mode=OperatingMode.IDLE.value,
        session_id=None,
        satellite=None,
        data_source="NONE",
        started_at=None,
        updated_at=now,
        status="idle",
    )


def read_runtime_state() -> RuntimeState:
    """Read the current shared runtime state."""

    try:
        if not STATE_FILE.exists():
            return _default_state()

        raw = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(raw, dict):
            return _default_state()

        mode = _normalise_mode(
            raw.get(
                "mode",
                OperatingMode.IDLE.value,
            )
        )

        return RuntimeState(
            mode=mode,
            session_id=raw.get("session_id"),
            satellite=raw.get("satellite"),
            data_source=str(
                raw.get(
                    "data_source",
                    "NONE",
                )
            ),
            started_at=raw.get("started_at"),
            updated_at=raw.get("updated_at"),
            status=str(
                raw.get(
                    "status",
                    "idle",
                )
            ),
        )

    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return _default_state()


def write_runtime_state(
    state: RuntimeState,
) -> RuntimeState:
    """Atomically write shared runtime state."""

    RUNTIME_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    state.updated_at = _utc_now()

    payload = json.dumps(
        state.to_dict(),
        indent=2,
        sort_keys=False,
    )

    fd, temporary_name = tempfile.mkstemp(
        prefix=".orbitwatch-state-",
        suffix=".tmp",
        dir=str(RUNTIME_DIRECTORY),
        text=True,
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(payload)
            handle.write("\n")

        os.replace(
            temporary_name,
            STATE_FILE,
        )

    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass

        raise

    return state


def set_idle() -> RuntimeState:
    """Set OrbitWatch to idle."""

    return write_runtime_state(
        RuntimeState(
            mode=OperatingMode.IDLE.value,
            session_id=None,
            satellite=None,
            data_source="NONE",
            started_at=None,
            status="idle",
        )
    )


def set_replay(
    session_id: str | None = None,
    satellite: str | None = None,
) -> RuntimeState:
    """Mark the current process as a replay/development session."""

    return write_runtime_state(
        RuntimeState(
            mode=OperatingMode.REPLAY.value,
            session_id=session_id,
            satellite=satellite,
            data_source="REPLAY",
            started_at=_utc_now(),
            status="running",
        )
    )


def set_live(
    session_id: str | None = None,
    satellite: str | None = None,
) -> RuntimeState:
    """Mark OrbitWatch as live only after real receive-side activation."""

    return write_runtime_state(
        RuntimeState(
            mode=OperatingMode.LIVE.value,
            session_id=session_id,
            satellite=satellite,
            data_source="SDR",
            started_at=_utc_now(),
            status="receiving",
        )
    )


def runtime_state_dict() -> dict[str, Any]:
    """Return the current state as a JSON-compatible dictionary."""

    return read_runtime_state().to_dict()


def reset_runtime_state() -> RuntimeState:
    """Return runtime state to a clean IDLE state."""

    return set_idle()
