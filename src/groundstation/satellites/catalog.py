"""
Satellite catalog management for OrbitWatch.

The catalog stores satellite identity and radio/protocol metadata.
Orbital calculations are implemented separately in orbit.py.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class Satellite:
    """Metadata describing a tracked satellite."""

    name: str
    norad_id: int
    international_designator: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    frequency_hz: float | None = None
    protocol: str | None = None
    tle_line1: str | None = None
    tle_line2: str | None = None

    def __post_init__(self) -> None:
        self.name = str(self.name).strip()

        if not self.name:
            raise ValueError(
                "Satellite name cannot be empty."
            )

        try:
            self.norad_id = int(self.norad_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "NORAD ID must be an integer."
            ) from exc

        if self.norad_id <= 0:
            raise ValueError(
                "NORAD ID must be positive."
            )

        self.aliases = tuple(
            str(alias).strip()
            for alias in self.aliases
            if alias is not None
            and str(alias).strip()
        )

        if self.frequency_hz is not None:
            try:
                self.frequency_hz = float(
                    self.frequency_hz
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Frequency must be numeric."
                ) from exc

            if (
                not math.isfinite(
                    self.frequency_hz
                )
                or self.frequency_hz <= 0
            ):
                raise ValueError(
                    "Frequency must be positive and finite."
                )

        if self.international_designator is not None:
            self.international_designator = (
                str(
                    self.international_designator
                ).strip()
                or None
            )

        if self.protocol is not None:
            self.protocol = (
                str(self.protocol).strip()
                or None
            )

        if self.tle_line1 is not None:
            self.tle_line1 = str(
                self.tle_line1
            ).strip() or None

        if self.tle_line2 is not None:
            self.tle_line2 = str(
                self.tle_line2
            ).strip() or None

    @property
    def identifier(self) -> str:
        """Return a stable human-readable satellite identifier."""

        return f"NORAD-{self.norad_id}"

    @property
    def has_tle(self) -> bool:
        """Return True when both TLE lines are available."""

        return bool(
            self.tle_line1
            and self.tle_line2
        )

    def matches(self, query: str) -> bool:
        """
        Return True when query matches satellite metadata.

        Matching is case-insensitive and supports partial matches
        for names, aliases and international designators.
        """

        query = str(query).strip().lower()

        if not query:
            return False

        if query == str(self.norad_id):
            return True

        if query == self.identifier.lower():
            return True

        if query in self.name.lower():
            return True

        if (
            self.international_designator
            and query
            in self.international_designator.lower()
        ):
            return True

        return any(
            query in alias.lower()
            for alias in self.aliases
        )

    def to_dict(self) -> dict:
        """Serialize the satellite to a JSON-compatible dictionary."""

        data = asdict(self)
        data["aliases"] = list(self.aliases)

        return data

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "Satellite":
        """Create a Satellite from a dictionary."""

        if not isinstance(data, dict):
            raise TypeError(
                "Satellite data must be a dictionary."
            )

        if "name" not in data:
            raise ValueError(
                "Satellite data is missing 'name'."
            )

        if "norad_id" not in data:
            raise ValueError(
                "Satellite data is missing 'norad_id'."
            )

        aliases = data.get(
            "aliases",
            (),
        )

        if isinstance(aliases, str):
            aliases = (aliases,)

        return cls(
            name=data["name"],
            norad_id=int(data["norad_id"]),
            international_designator=data.get(
                "international_designator"
            ),
            aliases=tuple(aliases),
            frequency_hz=(
                float(data["frequency_hz"])
                if data.get("frequency_hz")
                is not None
                else None
            ),
            protocol=data.get("protocol"),
            tle_line1=data.get("tle_line1"),
            tle_line2=data.get("tle_line2"),
        )


class SatelliteCatalog:
    """In-memory satellite catalog with JSON persistence."""

    def __init__(
        self,
        satellites: Iterable[Satellite] | None = None,
    ) -> None:
        self._satellites: dict[int, Satellite] = {}

        if satellites is not None:
            for satellite in satellites:
                self.add(satellite)

    def __len__(self) -> int:
        return len(self._satellites)

    def __iter__(self):
        return iter(
            self._satellites.values()
        )

    def __contains__(
        self,
        norad_id: object,
    ) -> bool:
        try:
            value = int(norad_id)
        except (TypeError, ValueError):
            return False

        return value in self._satellites

    def add(
        self,
        satellite: Satellite,
    ) -> None:
        """Add or replace a satellite by NORAD ID."""

        if not isinstance(
            satellite,
            Satellite,
        ):
            raise TypeError(
                "Expected a Satellite instance."
            )

        self._satellites[
            satellite.norad_id
        ] = satellite

    def remove(
        self,
        norad_id: int,
    ) -> Satellite | None:
        """Remove and return a satellite, or None when absent."""

        return self._satellites.pop(
            int(norad_id),
            None,
        )

    def get(
        self,
        norad_id: int,
    ) -> Satellite | None:
        """Return a satellite by NORAD ID."""

        return self._satellites.get(
            int(norad_id)
        )

    def find(
        self,
        query: str,
    ) -> list[Satellite]:
        """Search satellites by metadata."""

        return [
            satellite
            for satellite in self._satellites.values()
            if satellite.matches(query)
        ]

    def all(self) -> list[Satellite]:
        """Return all satellites sorted by name."""

        return sorted(
            self._satellites.values(),
            key=lambda satellite:
                satellite.name.lower(),
        )

    def to_dict(self) -> dict:
        """Serialize the complete catalog."""

        return {
            "satellites": [
                satellite.to_dict()
                for satellite in self.all()
            ]
        }

    def to_json(
        self,
        path: str | Path,
    ) -> Path:
        """Write the catalog to JSON."""

        destination = Path(path)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination.write_text(
            json.dumps(
                self.to_dict(),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return destination

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "SatelliteCatalog":
        """Create a catalog from a dictionary."""

        if not isinstance(data, dict):
            raise TypeError(
                "Catalog data must be a dictionary."
            )

        satellites_data = data.get(
            "satellites",
            [],
        )

        if not isinstance(
            satellites_data,
            list,
        ):
            raise ValueError(
                "Catalog 'satellites' must be a list."
            )

        satellites = [
            Satellite.from_dict(item)
            for item in satellites_data
        ]

        return cls(satellites)

    @classmethod
    def from_json(
        cls,
        path: str | Path,
    ) -> "SatelliteCatalog":
        """Load a catalog from JSON."""

        source = Path(path)

        if not source.exists():
            raise FileNotFoundError(
                f"Satellite catalog not found: {source}"
            )

        data = json.loads(
            source.read_text(
                encoding="utf-8"
            )
        )

        return cls.from_dict(data)
