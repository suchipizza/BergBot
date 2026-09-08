"""Record live adapter responses into tests/fixtures/sources/<adapter>.json for offline contract tests.

Run: uv run python scripts/record_fixtures.py   (needs network; commits small JSON files)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bergbot.sources.base import Query  # noqa: E402
from bergbot.sources.http import HttpFetcher  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "sources"
BRUNNEN_BBOX = (8.55, 46.95, 8.70, 47.05)
TICINO_BBOX = (8.9, 46.1, 9.0, 46.2)
GR_BBOX = (9.65, 46.75, 9.85, 46.90)
BE_BBOX = (7.75, 46.85, 7.95, 47.0)
SNP_BBOX = (10.15, 46.62, 10.25, 46.68)
UR_BBOX = (8.2, 46.85, 8.35, 46.95)
LINE = {"type": "LineString", "coordinates": [[8.6069, 46.9945], [8.6215, 46.9990], [8.6318, 47.0059]]}


def rec(name: str):  # type: ignore[no-untyped-def]
    path = OUT / f"{name}.json"
    if path.exists():
        path.unlink()
    return HttpFetcher(record_to=path)


def main() -> None:
    from bergbot.sources.ch.army import ArmyShootingAdapter
    from bergbot.sources.ch.bafu import FireDangerAdapter, ProtectedAreasAdapter, QuietZonesAdapter
    from bergbot.sources.ch.closures import ClosuresAdapter
    from bergbot.sources.ch.geoadmin import GeoAdminAdapter
    from bergbot.sources.ch.guardian_dogs import GuardianDogsAdapter
    from bergbot.sources.ch.hiking_network import HikingNetworkAdapter, WanderlandRoutesAdapter
    from bergbot.sources.ch.meteoswiss import MeteoSwissAdapter
    from bergbot.sources.ch.slf import SLFAdapter
    from bergbot.sources.ch.transport import TransportAdapter
    from bergbot.sources.shared.osm import OSMAdapter

    g = GeoAdminAdapter(rec("geoadmin"))
    g.search("Brunnen SZ", limit=5)
    g.search("Brunnen", limit=8)
    g.search("Rigi Kulm", limit=5)
    g.search("Urnerboden", limit=5)
    g.search("Zürich HB", limit=3)
    g.profile(LINE, nb_points=50)
    g.height(8.61, 46.99)
    g.canton(8.61, 46.99)
    g.canton(8.48, 47.05)

    HikingNetworkAdapter(rec("hiking_network")).fetch(Query(kind="trails", bbox=(8.60, 46.99, 8.62, 47.01)))
    WanderlandRoutesAdapter(rec("wanderland")).fetch(Query(kind="routes", bbox=(8.60, 46.99, 8.62, 47.01)))
    ClosuresAdapter(rec("closures")).fetch(Query(kind="closures", bbox=UR_BBOX))
    ClosuresAdapter(rec("closures_brunnen")).fetch(Query(kind="closures", bbox=BRUNNEN_BBOX))
    MeteoSwissAdapter(rec("meteoswiss")).forecast(8.61, 46.99, 1500, forecast_days=3)
    QuietZonesAdapter(rec("quiet_zones")).fetch(Query(kind="quiet_zones", bbox=GR_BBOX))
    ProtectedAreasAdapter(rec("protected_areas")).fetch(Query(kind="protected_areas", bbox=SNP_BBOX))
    FireDangerAdapter(rec("fire")).fetch(Query(kind="fire_danger", bbox=TICINO_BBOX))
    GuardianDogsAdapter(rec("guardian_dogs")).fetch(Query(kind="guardian_dogs", bbox=GR_BBOX))
    ArmyShootingAdapter(rec("army")).fetch(Query(kind="shooting_zones", bbox=BE_BBOX))
    t = TransportAdapter(rec("transport"))
    t.stops_near(8.61, 46.99)
    t.connections("Zürich HB", "Brunnen", "2026-09-09", "07:00")
    t.connections("Brunnen", "Zürich HB", "2026-09-09", "17:00")
    SLFAdapter(rec("slf")).bulletins("en")
    OSMAdapter(rec("osm")).amenities(BRUNNEN_BBOX)
    print("recorded into", OUT)


if __name__ == "__main__":
    main()
