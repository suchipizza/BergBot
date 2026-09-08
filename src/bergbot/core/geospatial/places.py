"""Place resolution: text / 'lat,lon' / GPX → canonical `Place` with canton and elevation (via ch.geoadmin)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bergbot.core.domain import Evidence, EvidenceClass, Place, PlaceKind
from bergbot.sources.base import SourceUnavailable
from bergbot.sources.ch.geoadmin import GeoAdminAdapter
from bergbot.sources.http import Fetcher

_COORD = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")

OBJECTCLASS_TO_KIND = {
    "TLM_HALTESTELLE": PlaceKind.stop,
    "TLM_HUETTE": PlaceKind.hut,
    "TLM_GIPFEL": PlaceKind.summit,
    "TLM_SIEDLUNGSNAME": PlaceKind.locality,
    "TLM_FLURNAME": PlaceKind.locality,
    "TLM_GEBAEUDE": PlaceKind.address,
    "TLM_GEMEINDEGEBIET": PlaceKind.municipality,
}

# Words that mark a summit/hut in the label when objectclass is generic
_SUMMIT_HINT = re.compile(r"\b(horn|spitz|stock|gipfel|kulm|piz|cima|pointe|mont|dent|grat|first)\b", re.I)
_HUT_HINT = re.compile(r"\b(hütte|hutte|cabane|capanna|rifugio|SAC|CAS)\b", re.I)
_LIFT_HINT = re.compile(
    r"\b(bergstation|talstation|seilbahn|luftseilbahn|gondel|sessel|bahn|téléphérique|funivia|télécabine)\b",
    re.I,
)


def resolve_place(text: str, lang: str = "en", fetcher: Fetcher | None = None) -> Place:
    text = text.strip()
    if not text:
        raise LookupError("empty place")
    if Path(text).suffix.lower() in (".gpx", ".kml", ".geojson") and Path(text).exists():
        from bergbot.core.geospatial.parse import parse_route_file

        route = parse_route_file(Path(text))
        lon, lat = route.coords[0][0], route.coords[0][1]
        p = Place(name=route.name, kind=PlaceKind.route_point, lon=lon, lat=lat, source="file")
        return _enrich(p, fetcher)
    m = _COORD.match(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        lat, lon = (a, b) if 45.0 <= a <= 48.0 else (b, a)
        p = Place(name=f"{lat:.5f}, {lon:.5f}", kind=PlaceKind.coordinates, lon=lon, lat=lat, source="user")
        return _enrich(p, fetcher)
    g = GeoAdminAdapter(fetcher)
    query, canton_hint = _split_canton(text)
    try:
        recs = g.search(query, limit=8)
    except SourceUnavailable as e:
        raise LookupError(f"could not resolve '{text}': {e}") from e
    if not recs:
        raise LookupError(f"no place found for '{text}'")
    recs.sort(key=lambda r: _rank_key(r.payload, query, canton_hint))
    if canton_hint is None:
        recs = _prefer_place_with_stop(recs, query, g)
    r = recs[0]
    label = r.payload["label"]
    kind = OBJECTCLASS_TO_KIND.get(str(r.payload.get("objectclass")), PlaceKind.unknown)
    if r.payload.get("origin") == "gg25":
        kind = PlaceKind.municipality
    elif r.payload.get("origin") == "haltestellen" or (r.payload.get("kind_label") or "").lower() in (
        "bus",
        "bahn",
        "zug",
        "schiff",
        "tram",
        "haltestelle",
    ):
        kind = PlaceKind.stop
    if kind is PlaceKind.unknown or kind is PlaceKind.locality:
        if _HUT_HINT.search(label):
            kind = PlaceKind.hut
        elif _LIFT_HINT.search(label):
            kind = PlaceKind.lift_station
        elif _SUMMIT_HINT.search(label) and kind is PlaceKind.unknown:
            kind = PlaceKind.summit
    name = re.sub(r"\s*\((?:[A-Z]{2})\)(?:\s*-.*)?$", "", label).strip() or label
    canton_m = re.search(r"\(([A-Z]{2})\)", label)
    p = Place(
        name=name,
        kind=kind,
        lon=float(r.payload["lon"]),
        lat=float(r.payload["lat"]),
        canton=canton_m.group(1).lower() if canton_m else None,
        bbox=r.payload.get("bbox"),
        source="ch.geoadmin",
        evidence=[
            Evidence(
                **{"class": EvidenceClass.A},
                source="ch.geoadmin",
                url=r.url,
                retrieved_ts=r.retrieved_ts,
                original_span=label[:80],
            )
        ],
    )
    return _enrich(p, fetcher)


CANTONS = {
    "ag",
    "ai",
    "ar",
    "be",
    "bl",
    "bs",
    "fr",
    "ge",
    "gl",
    "gr",
    "ju",
    "lu",
    "ne",
    "nw",
    "ow",
    "sg",
    "sh",
    "so",
    "sz",
    "tg",
    "ti",
    "ur",
    "vd",
    "vs",
    "zg",
    "zh",
}

_CLASS_PRIORITY = {
    "TLM_SIEDLUNGSNAME": 0,
    "TLM_GEMEINDEGEBIET": 0,
    "TLM_NAME_PKT": 1,
    "TLM_HALTESTELLE": 1,
    "TLM_HUETTE": 1,
    "TLM_GIPFEL": 1,
    "TLM_UEBRIGE_BAHN": 2,
    "TLM_FLURNAME": 3,
    "TLM_GEBAEUDE": 4,
    "TLM_STRASSE": 5,
}


def _split_canton(text: str) -> tuple[str, str | None]:
    """'Brunnen SZ' → ('Brunnen', 'sz'); 'Rigi Kulm' → ('Rigi Kulm', None)."""
    parts = text.replace(",", " ").split()
    if len(parts) >= 2 and parts[-1].lower() in CANTONS and parts[-1].isupper():
        return " ".join(parts[:-1]), parts[-1].lower()
    return text, None


def _rank_key(payload: dict[str, Any], query: str, canton_hint: str | None) -> tuple[int, int, int, int, int]:
    label = payload["label"]
    name = re.split(r"\s*\(", label, maxsplit=1)[0].strip().lower()
    q = query.lower().strip()
    exact = 0 if name == q else 1 if name.startswith(q) or q in name else 2
    canton_m = re.search(r"\(([A-Z]{2})\)", label)
    canton_ok = 0 if (canton_hint is None or (canton_m and canton_m.group(1).lower() == canton_hint)) else 1
    cls = _CLASS_PRIORITY.get(str(payload.get("objectclass") or "").upper(), 3)
    origin = {"gg25": 0, "district": 1, "haltestellen": 1, "gazetteer": 2}.get(
        str(payload.get("origin") or ""), 2
    )
    return (canton_ok, exact, origin, cls, -(payload.get("weight") or 0))


def _prefer_place_with_stop(recs: list[Any], query: str, g: GeoAdminAdapter) -> list[Any]:
    """Several localities share a name (Brunnen SZ / VS / SG…). A place that has a public-transport stop of the
    same name is almost always the one people mean; GeoAdmin lists stops with origin 'haltestellen'."""
    q = query.lower().strip()
    exact = [r for r in recs if re.split(r"\s*\(", r.payload["label"], maxsplit=1)[0].strip().lower() == q]
    if len(exact) < 2:
        return recs
    try:
        stops = [
            s
            for s in g.search(query, limit=10, origins="haltestellen")
            if s.payload["label"].split(",")[0].strip().lower() == q
        ]
    except SourceUnavailable:
        return recs

    def near_stop(r: Any) -> int:
        for s_ in stops:
            if (
                abs(s_.payload["lat"] - r.payload["lat"]) < 0.03
                and abs(s_.payload["lon"] - r.payload["lon"]) < 0.04
            ):
                return 0
        return 1

    return sorted(recs, key=near_stop)


def _enrich(p: Place, fetcher: Fetcher | None) -> Place:
    g = GeoAdminAdapter(fetcher)
    if p.canton is None:
        try:
            c = g.canton(p.lon, p.lat)
            if c:
                p.canton = c.payload["code"]
        except SourceUnavailable:
            pass
    if p.elevation_m is None:
        try:
            p.elevation_m = g.height(p.lon, p.lat).payload["height_m"]
        except SourceUnavailable:
            pass
    return p


def now() -> datetime:
    return datetime.now(tz=UTC)
