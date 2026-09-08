"""Huts, restaurants, water, shelters, lifts, parking near the route (OSM). Status is `unverified` by design;
lifts and huts within reach yield `lift_unverified` / `hut_unverified` notes carrying the web-verification spec."""

from __future__ import annotations

from bergbot.core.domain import (
    Amenity,
    AmenityKind,
    Evidence,
    EvidenceClass,
    Route,
    Severity,
    Warning,
    WarningType,
)
from bergbot.core.geospatial.ops import distance_to_route_m, route_bbox
from bergbot.sources.base import Query, SourceUnavailable
from bergbot.sources.http import Fetcher
from bergbot.sources.shared.osm import OSMAdapter
from bergbot.sources.shared.web import verification_spec

NEAR_M = {
    "hut": 400.0,
    "restaurant": 120.0,
    "water": 100.0,
    "shelter": 200.0,
    "lift": 300.0,
    "parking": 300.0,
    "poi": 150.0,
}
MAX_PER_KIND = {"restaurant": 6, "water": 8, "parking": 3, "poi": 4, "shelter": 4, "hut": 6, "lift": 4}


def nearby_amenities(
    route: Route, date: str, fetcher: Fetcher | None = None, offline: bool = False
) -> tuple[list[Amenity], list[Warning], list[str]]:
    if offline:
        return [], [], ["shared.osm"]
    try:
        recs = OSMAdapter(fetcher).fetch(Query(kind="amenities", bbox=route_bbox(route.coords, pad_m=500)))
    except SourceUnavailable:
        return [], [], ["shared.osm"]
    out: list[Amenity] = []
    warnings: list[Warning] = []
    seen: set[tuple[str, str]] = set()
    for r in recs:
        d, km = distance_to_route_m(route.coords, r.payload["lon"], r.payload["lat"])
        if d > NEAR_M.get(r.kind, 200.0):
            continue
        name = r.payload.get("name") or r.kind
        if r.kind in ("lift", "hut", "restaurant") and not r.payload.get("name"):
            continue
        if (r.kind, name) in seen:
            continue
        seen.add((r.kind, name))
        ev = Evidence(
            **{"class": EvidenceClass.A},
            source="shared.osm",
            url=r.url,
            retrieved_ts=r.retrieved_ts,
            confidence=0.7,
            translated_summary=f"OSM {r.kind}: {name}",
        )
        a = Amenity(
            kind=AmenityKind(r.kind),
            name=name,
            lon=r.payload["lon"],
            lat=r.payload["lat"],
            km=round(km, 1),
            distance_m=round(d),
            evidence=[ev],
            url=(r.payload.get("tags") or {}).get("website"),
        )
        out.append(a)
        if r.kind == "lift":
            warnings.append(
                Warning(
                    type=WarningType.lift_unverified,
                    severity=Severity.note,
                    evidence=[ev],
                    params={
                        "name": name,
                        "date": date,
                        "web_verification": verification_spec(
                            "lift_status", subject=name, name=name, date=date
                        ),
                    },
                )
            )
        elif r.kind == "hut":
            warnings.append(
                Warning(
                    type=WarningType.hut_unverified,
                    severity=Severity.note,
                    evidence=[ev],
                    params={
                        "name": name,
                        "date": date,
                        "web_verification": verification_spec("hut_open", subject=name, name=name, date=date),
                    },
                )
            )
    # cap per kind, nearest to the route first
    capped: list[Amenity] = []
    for kind, cap in MAX_PER_KIND.items():
        capped.extend(
            sorted([a for a in out if a.kind.value == kind], key=lambda a: (a.distance_m or 0.0, a.name))[
                :cap
            ]
        )
    keep = {(a.kind.value, a.name) for a in capped}
    warnings = [
        w
        for w in warnings
        if (("lift" if w.type is WarningType.lift_unverified else "hut"), w.params.get("name")) in keep
    ]
    capped.sort(key=lambda a: (a.km or 0.0, a.name))
    return capped, warnings, []
