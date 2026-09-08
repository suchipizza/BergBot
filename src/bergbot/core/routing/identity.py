"""Match a route against SwitzerlandMobility named routes (identity) and the official trail network (membership)."""

from __future__ import annotations

from typing import Any

from shapely.geometry import shape
from shapely.ops import unary_union

from bergbot.core.domain import Difficulty, DifficultySystem, Evidence, EvidenceClass, Route, RouteIdentity
from bergbot.core.geospatial.ops import metric_route, overlap_fraction, route_bbox, to_metric
from bergbot.sources.base import Query, SourceUnavailable
from bergbot.sources.ch.hiking_network import HikingNetworkAdapter, WanderlandRoutesAdapter
from bergbot.sources.http import Fetcher


def identify(
    route: Route, fetcher: Fetcher | None = None
) -> tuple[RouteIdentity, Difficulty, list[Evidence], list[str]]:
    """Returns (identity, difficulty hint, evidence, unavailable sources)."""
    unavailable: list[str] = []
    evidence: list[Evidence] = []
    bbox = route_bbox(route.coords, pad_m=200)
    identity = route.identity.model_copy()
    difficulty = route.difficulty.model_copy()

    # named routes
    try:
        recs = WanderlandRoutesAdapter(fetcher).fetch(Query(kind="routes", bbox=bbox))
        best: tuple[float, Any] | None = None
        for r in recs:
            g = r.payload.get("geometry")
            if not g:
                continue
            frac = overlap_fraction(route.coords, g, buffer_m=30.0)
            if best is None or frac > best[0]:
                best = (frac, r)
        if best and best[0] >= 0.6:
            r = best[1]
            identity.name = identity.name or r.payload.get("name")
            identity.official_id = str(r.payload.get("feature_id"))
            identity.network = "ch.astra.wanderland"
            identity.overlap_pct = round(best[0] * 100, 1)
            if r.payload.get("prominence") in ("national", "regional"):
                identity.famous = True
                identity.famous_reason = (
                    f"SwitzerlandMobility {r.payload.get('prominence')} route {r.payload.get('route_number')}"
                )
            evidence.append(
                Evidence(
                    **{"class": EvidenceClass.B},
                    source="ch.hiking_network.wanderland",
                    url=r.url,
                    retrieved_ts=r.retrieved_ts,
                    confidence=min(1.0, best[0]),
                    translated_summary=f"{identity.overlap_pct}% of the route overlaps '{r.payload.get('name')}'",
                )
            )
    except SourceUnavailable:
        unavailable.append("ch.hiking_network.wanderland")

    # network membership + grade hint — fetched per 4 km cell along the route (GeoAdmin caps identify at 200)
    try:
        from shapely.geometry import LineString, box

        from bergbot.core.routing.candidates import tiles

        line = LineString([(c[0], c[1]) for c in route.coords]).buffer(0.002)
        adapter = HikingNetworkAdapter(fetcher)
        segs = []
        seen: set[str] = set()
        for cell in tiles(bbox, cell_km=4.0):
            if not box(*cell).intersects(line):
                continue
            for r in adapter.fetch(Query(kind="trails", bbox=cell)):
                fid = str(r.payload.get("feature_id"))
                if fid not in seen:
                    seen.add(fid)
                    segs.append(r)
        geoms = [to_metric(shape(s.payload["geometry"])) for s in segs if s.payload.get("geometry")]
        if geoms:
            union = unary_union(geoms).buffer(30.0)
            mr = metric_route(route.coords)
            on = float(mr.line.intersection(union).length / mr.line.length) if mr.line.length else 0.0
            route.network_member = on >= 0.9
            hints = [s.payload.get("grade_hint") for s in segs if s.payload.get("grade_hint")]
            if hints and difficulty.grade is None:
                worst = max(hints, key=lambda h: int(str(h)[1]))
                difficulty = Difficulty(
                    system=DifficultySystem.sac_t,
                    grade=str(worst),
                    source="ch.hiking_network (trail category)",
                    confidence=0.5,
                )
            evidence.append(
                Evidence(
                    **{"class": EvidenceClass.B},
                    source="ch.hiking_network",
                    retrieved_ts=segs[0].retrieved_ts,
                    confidence=0.9,
                    translated_summary=f"{round(on * 100)}% of the route lies on the official hiking network",
                )
            )
        else:
            route.network_member = False
    except SourceUnavailable:
        unavailable.append("ch.hiking_network")
    return identity, difficulty, evidence, unavailable
