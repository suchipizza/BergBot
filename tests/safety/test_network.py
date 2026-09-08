"""SR-5: candidate routes are subsets of the official network — every candidate vertex lies within 30 m of
a swissTLM3D hiking segment fetched for the same area."""

from __future__ import annotations

from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import unary_union

from bergbot.core.domain import Activity, Constraint
from bergbot.core.geospatial.crs import to_lv95
from bergbot.core.geospatial.ops import to_metric
from bergbot.core.geospatial.places import resolve_place
from bergbot.core.routing.candidates import (
    graph_candidates,
    named_stage_candidates,
    radius_for,
    search_bbox,
    tiles,
)
from bergbot.sources.base import Query
from bergbot.sources.ch.hiking_network import HikingNetworkAdapter
from bergbot.sources.http import FixtureFetcher

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _fetcher() -> FixtureFetcher:
    f = FixtureFetcher.from_files(
        FIX / "workflows" / "session.json.gz", *sorted((FIX / "sources").glob("*.json"))
    )
    f.strict = False
    return f


def test_graph_candidates_lie_on_network() -> None:
    f = _fetcher()
    place = resolve_place("Brunnen", fetcher=f)
    c = Constraint(date="2026-09-12")
    bbox = search_bbox(place, radius_for(c, place))
    cands = graph_candidates(place, bbox, c, f, Activity.hiking)
    assert cands, "no graph candidates from fixtures"
    graph_bbox = search_bbox(place, min(3.5, radius_for(c)))
    geoms = []
    for cell in tiles(graph_bbox):
        for r in HikingNetworkAdapter(f).fetch(Query(kind="trails", bbox=cell)):
            if r.payload.get("geometry"):
                geoms.append(to_metric(shape(r.payload["geometry"])))
    network = unary_union(geoms).buffer(30.0)
    for cand in cands:
        assert cand.network_member and cand.is_loop
        for lon, lat in (c[:2] for c in cand.coords):
            assert network.contains(Point(*to_lv95(lon, lat))), f"{cand.name} leaves the network"


def test_named_candidates_come_from_official_layer() -> None:
    f = _fetcher()
    place = resolve_place("Brunnen", fetcher=f)
    bbox = search_bbox(place, 6.0)
    for r in named_stage_candidates(bbox, f, Activity.hiking):
        assert r.identity.network == "ch.astra.wanderland" and r.network_member
