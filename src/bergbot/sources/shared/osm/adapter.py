"""Overpass API (ODbL). Query kind `amenities`: bbox → nodes/ways (centroids) tagged as alpine huts, restaurants,
drinking water, shelters, viewpoints, parking, aerialway stations. Cached 7 days per bbox."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.http import Fetcher, default_fetcher

OVERPASS = "https://overpass-api.de/api/interpreter"

TAG_TO_KIND = [
    ("tourism", "alpine_hut", "hut"),
    ("tourism", "wilderness_hut", "shelter"),
    ("amenity", "shelter", "shelter"),
    ("amenity", "restaurant", "restaurant"),
    ("amenity", "cafe", "restaurant"),
    ("amenity", "drinking_water", "water"),
    ("natural", "spring", "water"),
    ("amenity", "parking", "parking"),
    ("aerialway", "station", "lift"),
    ("tourism", "viewpoint", "poi"),
]


def build_query(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox[1], bbox[0], bbox[3], bbox[2]
    bb = f"({s:.5f},{w:.5f},{n:.5f},{e:.5f})"
    parts = []
    for k, v, _ in TAG_TO_KIND:
        parts.append(f'nwr["{k}"="{v}"]{bb};')
    return f"[out:json][timeout:40];({''.join(parts)});out center tags;"


class OSMAdapter:
    id = "shared.osm"
    kinds: ClassVar[tuple[str, ...]] = ("amenities",)
    ttl_s: ClassVar[int] = 7 * 86400

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None
        self._latency: int | None = None

    def fetch(self, query: Query) -> list[Record]:
        if not query.bbox:
            raise ValueError("amenities needs bbox")
        return self.amenities(query.bbox)

    def amenities(self, bbox: tuple[float, float, float, float]) -> list[Record]:
        q = build_query(bbox)
        res = self.fetcher.get_json(
            self.id, OVERPASS, None, ttl_s=self.ttl_s, method="POST", data="data=" + q, what="OSM amenities"
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        out: list[Record] = []
        for el in res.data.get("elements", []):
            tags = el.get("tags") or {}
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            kind = next((k for tk, tv, k in TAG_TO_KIND if tags.get(tk) == tv), "poi")
            out.append(
                Record(
                    source_id=self.id,
                    kind=kind,
                    payload={
                        "osm_id": f"{el.get('type')}/{el.get('id')}",
                        "name": tags.get("name")
                        or tags.get("name:de")
                        or tags.get("name:fr")
                        or tags.get("name:it"),
                        "lat": lat,
                        "lon": lon,
                        "tags": {
                            k: v
                            for k, v in tags.items()
                            if k
                            in (
                                "name",
                                "ele",
                                "website",
                                "phone",
                                "opening_hours",
                                "operator",
                                "shelter_type",
                                "fee",
                                "aerialway",
                                "capacity",
                                "seasonal",
                                "wikipedia",
                            )
                        },
                    },
                    retrieved_ts=res.retrieved_ts,
                    url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
                )
            )
        return out

    def freshness(self) -> Freshness:
        return Freshness(source_ts=None, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return Licence(
            name="ODbL 1.0",
            redistribution=True,
            attribution="© OpenStreetMap contributors",
            url="https://www.openstreetmap.org/copyright",
        )

    def health(self) -> Health:
        try:
            self.amenities((8.55, 46.95, 8.70, 47.05))
            return Health(ok=True, latency_ms=self._latency, last_success_ts=self._last)
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))


def now() -> datetime:
    return datetime.now(tz=UTC)
