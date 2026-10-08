"""
Tests for the OrbitWatch satellite catalog subsystem.
"""

from __future__ import annotations

import json

from groundstation.satellites import (
    Satellite,
    SatelliteCatalog,
)


def test_satellite_creation() -> None:
    satellite = Satellite(
        name="OrbitWatch TestSat",
        norad_id=12345,
        aliases=("OWTEST",),
        frequency_hz=145800000,
        protocol="AX.25",
    )

    assert satellite.name == "OrbitWatch TestSat"
    assert satellite.norad_id == 12345
    assert satellite.frequency_hz == 145800000
    assert satellite.protocol == "AX.25"
    assert "OWTEST" in satellite.aliases


def test_satellite_identifier() -> None:
    satellite = Satellite(
        name="TestSat",
        norad_id=12345,
    )

    assert satellite.identifier == "NORAD-12345"


def test_satellite_matching() -> None:
    satellite = Satellite(
        name="OrbitWatch TestSat",
        norad_id=12345,
        international_designator="2026-001A",
        aliases=("OWTEST",),
    )

    assert satellite.matches("orbitwatch")
    assert satellite.matches("12345")
    assert satellite.matches("owtest")
    assert satellite.matches("2026-001A")
    assert not satellite.matches("unknown")


def test_catalog_add_get_remove() -> None:
    catalog = SatelliteCatalog()

    satellite = Satellite(
        name="TestSat",
        norad_id=12345,
    )

    catalog.add(satellite)

    assert len(catalog) == 1
    assert catalog.get(12345) == satellite

    assert catalog.remove(12345)
    assert len(catalog) == 0
    assert catalog.get(12345) is None


def test_catalog_search() -> None:
    catalog = SatelliteCatalog(
        [
            Satellite(
                name="AlphaSat",
                norad_id=10001,
            ),
            Satellite(
                name="BetaSat",
                norad_id=10002,
            ),
        ]
    )

    results = catalog.find("alpha")

    assert len(results) == 1
    assert results[0].name == "AlphaSat"


def test_catalog_json_round_trip(tmp_path) -> None:
    path = tmp_path / "satellites.json"

    catalog = SatelliteCatalog(
        [
            Satellite(
                name="TestSat",
                norad_id=12345,
                aliases=("TEST",),
                frequency_hz=145800000,
                protocol="AX.25",
            )
        ]
    )

    catalog.to_json(path)

    assert path.exists()

    loaded = SatelliteCatalog.from_json(path)

    satellite = loaded.get(12345)

    assert satellite is not None
    assert satellite.name == "TestSat"
    assert satellite.aliases == ("TEST",)
    assert satellite.frequency_hz == 145800000
    assert satellite.protocol == "AX.25"


def test_catalog_json_structure(tmp_path) -> None:
    path = tmp_path / "satellites.json"

    catalog = SatelliteCatalog(
        [
            Satellite(
                name="TestSat",
                norad_id=12345,
            )
        ]
    )

    catalog.to_json(path)

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert "satellites" in data
    assert len(data["satellites"]) == 1
    assert data["satellites"][0]["norad_id"] == 12345
