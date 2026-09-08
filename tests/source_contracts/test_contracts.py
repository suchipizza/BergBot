"""FR-D2: every adapter honours the contract (fetch/freshness/licence/health), every Record has retrieved_ts,
and degradation is an exception (`SourceUnavailable`), never silence."""

from __future__ import annotations

from datetime import datetime

import pytest

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceAdapter, SourceUnavailable
from bergbot.sources.ch.army import ArmyShootingAdapter
from bergbot.sources.ch.bafu import FireDangerAdapter, ProtectedAreasAdapter, QuietZonesAdapter
from bergbot.sources.ch.closures import ClosuresAdapter
from bergbot.sources.ch.geoadmin import GeoAdminAdapter
from bergbot.sources.ch.guardian_dogs import GuardianDogsAdapter
from bergbot.sources.ch.hiking_network import HikingNetworkAdapter, WanderlandRoutesAdapter
from bergbot.sources.ch.meteoswiss import MeteoSwissAdapter
from bergbot.sources.ch.slf import SLFAdapter
from bergbot.sources.ch.swisstopo_tiles import SwisstopoTilesAdapter
from bergbot.sources.ch.transport import TransportAdapter
from bergbot.sources.http import FixtureFetcher
from bergbot.sources.registry import all_adapters
from bergbot.sources.shared.osm import OSMAdapter
from bergbot.sources.shared.web import VERIFICATION_SPECS, WebVerification, verification_spec

GR = (9.65, 46.75, 9.85, 46.90)
BE = (7.75, 46.85, 7.95, 47.0)
UR = (8.2, 46.85, 8.35, 46.95)
SNP = (10.15, 46.62, 10.25, 46.68)
TI = (8.9, 46.1, 9.0, 46.2)
BRUNNEN = (8.55, 46.95, 8.70, 47.05)
TRAIL = (8.60, 46.99, 8.62, 47.01)

CASES = [
    (HikingNetworkAdapter, Query(kind="trails", bbox=TRAIL), "trail_segment"),
    (WanderlandRoutesAdapter, Query(kind="routes", bbox=TRAIL), "named_route"),
    (ClosuresAdapter, Query(kind="closures", bbox=UR), "closure"),
    (QuietZonesAdapter, Query(kind="quiet_zones", bbox=GR), "quiet_zone"),
    (ProtectedAreasAdapter, Query(kind="protected_areas", bbox=SNP), "protected_area"),
    (FireDangerAdapter, Query(kind="fire_danger", bbox=TI), "fire_danger"),
    (GuardianDogsAdapter, Query(kind="guardian_dogs", bbox=GR), "guardian_dog_area"),
    (ArmyShootingAdapter, Query(kind="shooting_zones", bbox=BE), "shooting_zone"),
    (OSMAdapter, Query(kind="amenities", bbox=BRUNNEN), None),
    (
        MeteoSwissAdapter,
        Query(kind="forecast", bbox=(8.61, 46.99, 8.61, 46.99), params={"elevation_m": 1500}),
        "forecast",
    ),
    (TransportAdapter, Query(kind="stops_near", bbox=(8.61, 46.99, 8.61, 46.99)), "stop"),
    (GeoAdminAdapter, Query(kind="search", text="Brunnen SZ", params={"limit": 5}), "place"),
]


def test_registry_lists_every_adapter_and_they_satisfy_protocol(fetcher: FixtureFetcher) -> None:
    ads = all_adapters(fetcher)
    ids = {a.id for a in ads}
    assert len(ids) == len(ads) == 14
    for a in ads:
        assert isinstance(a, SourceAdapter)
        assert isinstance(a.licence(), Licence)
        assert isinstance(a.freshness(), Freshness)
        assert a.licence().attribution


@pytest.mark.parametrize(("cls", "query", "kind"), CASES, ids=[c[0].__name__ for c in CASES])
def test_fetch_returns_records_with_timestamps(
    fetcher: FixtureFetcher, cls: type, query: Query, kind: str | None
) -> None:
    adapter = cls(fetcher)
    records = adapter.fetch(query)
    assert records, f"{adapter.id} returned nothing for fixture query"
    for r in records:
        assert isinstance(r, Record)
        assert r.source_id == adapter.id
        assert isinstance(r.retrieved_ts, datetime) and r.retrieved_ts.tzinfo is not None
        if kind:
            assert r.kind == kind or (
                adapter.id == "ch.bafu.fire" and r.kind in ("fire_danger", "fire_measures")
            )
        if r.original_span:
            assert len(r.original_span.split()) <= 15
    fr = adapter.freshness()
    assert fr.retrieved_ts is not None


def test_health_reports_ok_on_fixtures(fetcher: FixtureFetcher) -> None:
    for a in all_adapters(fetcher):
        if a.id == "ch.swisstopo_tiles":
            continue  # tiles are bytes; fixture fetcher has none → health false by design
        h = a.health()
        assert isinstance(h, Health)
        assert h.ok, f"{a.id}: {h.note}"


def test_unavailable_is_an_exception_not_silence() -> None:
    empty = FixtureFetcher(entries=[])
    with pytest.raises(SourceUnavailable):
        ClosuresAdapter(empty).fetch(Query(kind="closures", bbox=UR))
    with pytest.raises(SourceUnavailable):
        MeteoSwissAdapter(empty).forecast(8.6, 46.9)
    h = SwisstopoTilesAdapter(empty).health()
    assert h.ok is False


def test_closures_normalisation(fetcher: FixtureFetcher) -> None:
    recs = ClosuresAdapter(fetcher).fetch(Query(kind="closures", bbox=UR))
    r = recs[0]
    assert r.payload["closure_type"] in ("closed", "detour", "closure")
    assert set(r.payload["reason"]) == {"de", "fr", "it", "en"}
    assert r.payload["geometry"]["type"] in ("LineString", "MultiLineString")


def test_quiet_zone_rules(fetcher: FixtureFetcher) -> None:
    recs = QuietZonesAdapter(fetcher).fetch(Query(kind="quiet_zones", bbox=GR))
    assert any(r.payload["rule_code"] for r in recs)
    assert any(r.payload["name"] for r in recs)


def test_fire_danger_level_parsed(fetcher: FixtureFetcher) -> None:
    recs = FireDangerAdapter(fetcher).fetch(Query(kind="fire_danger", bbox=TI))
    danger = [r for r in recs if r.kind == "fire_danger"]
    measures = [r for r in recs if r.kind == "fire_measures"]
    assert danger and measures
    assert all(isinstance(r.payload["level"], int) for r in danger)
    assert all(r.source_ts is not None for r in danger)


def test_shooting_zone_has_weekdays_and_url(fetcher: FixtureFetcher) -> None:
    recs = ArmyShootingAdapter(fetcher).fetch(Query(kind="shooting_zones", bbox=BE))
    assert all(isinstance(r.payload["weekdays"], list) for r in recs)
    assert all(r.url and "armee.ch" in r.url for r in recs)


def test_forecast_shape(fetcher: FixtureFetcher) -> None:
    rec = MeteoSwissAdapter(fetcher).forecast(8.61, 46.99, 1500, forecast_days=3)
    hours = rec.payload["hours"]
    assert len(hours) == 72
    h = hours[12]
    assert h["temp_c"] is not None and h["gust_kmh"] is not None and h["summary"]
    assert rec.payload["sunset"]


def test_transport_connections(fetcher: FixtureFetcher) -> None:
    t = TransportAdapter(fetcher)
    out = t.connections("Zürich HB", "Brunnen", "2026-09-09", "07:00")
    assert out and out[0].payload["departure"].startswith("2026-09-09")
    back = t.connections("Brunnen", "Zürich HB", "2026-09-09", "17:00")
    assert back and back[0].payload["arrival"] > back[0].payload["departure"]


def test_geoadmin_search_profile_canton(fetcher: FixtureFetcher) -> None:
    g = GeoAdminAdapter(fetcher)
    places = g.search("Brunnen SZ", limit=5)
    assert places and "<" not in places[0].payload["label"]
    prof = g.profile(
        {"type": "LineString", "coordinates": [[8.6069, 46.9945], [8.6215, 46.9990], [8.6318, 47.0059]]},
        nb_points=50,
    )
    assert len(prof.payload["samples"]) >= 40 and prof.payload["samples"][-1]["dist_m"] > 1000
    assert g.canton(8.61, 46.99).payload["code"] == "sz"  # type: ignore[union-attr]
    assert g.height(8.61, 46.99).payload["height_m"] > 400


def test_slf_out_of_season_is_empty_not_error(fetcher: FixtureFetcher) -> None:
    assert SLFAdapter(fetcher).bulletins("en") == []


def test_osm_kinds(fetcher: FixtureFetcher) -> None:
    recs = OSMAdapter(fetcher).fetch(Query(kind="amenities", bbox=BRUNNEN))
    kinds = {r.kind for r in recs}
    assert {"water", "restaurant"} <= kinds


def test_web_spec_shape() -> None:
    for st in VERIFICATION_SPECS:
        spec = verification_spec(
            st,
            subject="Gemmi",
            name="Gemmibahn",
            date="2026-09-13",
            canton_name="Valais",
            region="Wallis",
            notice_id="1301.060",
        )
        assert spec["queries"] and spec["output_schema"]["title"] == "WebVerification"
        assert "{" not in " ".join(spec["queries"]), spec["queries"]
    wv = WebVerification(
        status_type="hut_open",
        subject="Glattalphütte",
        date="2026-09-13",
        result="unverified",
        retrieved_ts="2026-09-08T20:00:00Z",
    )
    assert wv.result == "unverified"
