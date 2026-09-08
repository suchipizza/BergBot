"""M3 acceptance: golden stats on 5 fixture GPX (distance ±1 %, ascent ±5 % vs reference)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bergbot.core.geospatial.ops import resample
from bergbot.core.geospatial.parse import parse_route_file
from bergbot.core.terrain.profile import build_profile, compute_stats

GPX = Path(__file__).resolve().parents[1] / "fixtures" / "gpx"

# reference: synthetic = exact construction; real = swissALTI3D profile recorded 2026-09-08
# (SwitzerlandMobility publishes Waldstätterweg Brunnen–Vitznau as 14 km / 600 m — within tolerance)
GOLDEN = {
    "synthetic-5km-400m": (5.00, 400.0, 0.0),
    "synthetic-loop-4km": (4.00, 600.0, 600.0),
    "waldstaetterweg-brunnen-vitznau": (14.43, 572.0, 572.0),
    "rigi-stage": (7.63, 1177.0, 32.0),
    "glarus-stage": (14.60, 988.0, 275.0),
}


@pytest.mark.parametrize("name", list(GOLDEN))
def test_golden(name: str, fixtures: Path) -> None:
    route = parse_route_file(GPX / f"{name}.gpx")
    route.geometry = {
        "type": "LineString",
        "coordinates": resample(route.coords, 25.0),
    }  # same step as audit_route
    if name.startswith("synthetic"):
        prof = build_profile(route, offline=True)  # elevations from the file
    else:
        from bergbot.sources.http import FixtureFetcher

        prof = build_profile(
            route, fetcher=FixtureFetcher.from_files(*sorted((fixtures / "workflows").glob("*.json.gz")))
        )
        assert prof.source == "ch.geoadmin"
    stats = compute_stats(route, prof)
    dist, up, down = GOLDEN[name]
    assert abs(stats.distance_km - dist) / dist <= 0.01, stats
    if up:
        assert abs(stats.ascent_m - up) / up <= 0.05, stats
    if down:
        assert abs(stats.descent_m - down) / max(down, 50) <= 0.05 or abs(stats.descent_m - down) <= 20, stats
    assert stats.duration_min > 0


def test_sac_duration_formula() -> None:
    from bergbot.core.terrain.profile import sac_duration_min

    # 8 km flat = 2 h; 800 m up over 4 km = max(1 h, 2 h) + 0.5 h = 2 h 30
    assert sac_duration_min(8, 0, 0) == 120
    assert sac_duration_min(4, 800, 0) == 150


def test_parse_kml_and_geojson(tmp_path: Path) -> None:
    kml = tmp_path / "r.kml"
    kml.write_text(
        '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>K</name><LineString><coordinates>8.6,46.99,450 8.61,46.995,500 8.62,47.0,520</coordinates></LineString></Placemark></Document></kml>'
    )
    r = parse_route_file(kml)
    assert r.name == "K" and len(r.coords) == 3 and r.coords[1][2] == 500
    gj = tmp_path / "r.geojson"
    gj.write_text(
        '{"type":"Feature","properties":{"name":"G"},"geometry":{"type":"LineString","coordinates":[[8.6,46.99],[8.61,46.995]]}}'
    )
    r2 = parse_route_file(gj)
    assert r2.name == "G" and len(r2.coords) == 2
