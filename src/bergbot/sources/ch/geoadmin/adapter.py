"""GeoAdmin core services: SearchServer (locations), profile.json (elevation along a line), height, canton.

Query kinds:
- `search`  text → candidate places (label, lat/lon, objectclass, detail)
- `profile` geometry (LineString WGS84) → elevation samples (dist_m, easting, northing, alt)
- `height`  bbox=(lon,lat,lon,lat) point → height
- `canton`  bbox point → canton code
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlencode

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.geoadmin_base import HEIGHT_URL, IDENTIFY_URL, OGD_LICENCE, PROFILE_URL, SEARCH_URL
from bergbot.sources.http import Fetcher, default_fetcher

_TAG = re.compile(r"<[^>]+>")
_KIND = re.compile(r"^\s*<i>([^<]*)</i>\s*")


class GeoAdminAdapter:
    id = "ch.geoadmin"
    kinds: ClassVar[tuple[str, ...]] = ("search", "profile", "height", "canton")
    ttl_s: ClassVar[int] = 7 * 86400

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None
        self._latency: int | None = None

    def fetch(self, query: Query) -> list[Record]:
        if query.kind == "search":
            return self.search(query.text or "", limit=int(query.params.get("limit", 8)))
        if query.kind == "profile":
            if not query.geometry:
                raise ValueError("profile needs geometry")
            return [self.profile(query.geometry, nb_points=int(query.params.get("nb_points", 200)))]
        if query.kind == "height":
            if not query.bbox:
                raise ValueError("height needs bbox point")
            return [self.height(query.bbox[0], query.bbox[1])]
        if query.kind == "canton":
            if not query.bbox:
                raise ValueError("canton needs bbox point")
            r = self.canton(query.bbox[0], query.bbox[1])
            return [r] if r else []
        raise ValueError(f"unknown kind {query.kind}")

    def freshness(self) -> Freshness:
        return Freshness(source_ts=None, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return OGD_LICENCE

    def health(self) -> Health:
        try:
            r = self.search("Brunnen", limit=8)
            return Health(ok=bool(r), latency_ms=self._latency, last_success_ts=self._last)
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))

    # -- services --
    def search(self, text: str, limit: int = 8) -> list[Record]:
        params = {"searchText": text, "type": "locations", "sr": 4326, "limit": limit}
        res = self.fetcher.get_json(
            self.id, SEARCH_URL, params, ttl_s=self.ttl_s, what=f"place search '{text}'"
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        out: list[Record] = []
        for r in res.data.get("results", []):
            a = r.get("attrs", {})
            if a.get("lat") is None or a.get("lon") is None:
                continue
            out.append(
                Record(
                    source_id=self.id,
                    kind="place",
                    payload={
                        "label": _TAG.sub("", _KIND.sub("", a.get("label", ""))).strip(),
                        "kind_label": (_KIND.match(a.get("label", "")) or [None, None])[1],
                        "detail": a.get("detail"),
                        "objectclass": a.get("objectclass"),
                        "origin": a.get("origin"),
                        "lat": a["lat"],
                        "lon": a["lon"],
                        "bbox": _box(a.get("geom_st_box2d")),
                        "rank": a.get("rank"),
                        "weight": r.get("weight"),
                    },
                    retrieved_ts=res.retrieved_ts,
                    url=f"https://map.geo.admin.ch/?swisssearch={text}",
                )
            )
        return out

    def profile(self, geometry: dict[str, Any], nb_points: int = 200) -> Record:
        """`geometry` is a WGS84 LineString; the service wants LV95, so convert first."""
        from bergbot.core.geospatial.crs import to_lv95

        lv95 = {
            "type": "LineString",
            "coordinates": [
                [round(e, 1), round(n, 1)] for e, n in (to_lv95(c[0], c[1]) for c in geometry["coordinates"])
            ],
        }
        body = urlencode(
            {"geom": json.dumps(lv95, separators=(",", ":")), "sr": 2056, "nb_points": nb_points}
        )
        res = self.fetcher.get_json(
            self.id, PROFILE_URL, None, ttl_s=self.ttl_s, method="POST", data=body, what="elevation profile"
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        samples = [
            {
                "dist_m": p["dist"],
                "alt_m": (p.get("alts") or {}).get("COMB"),
                "easting": p["easting"],
                "northing": p["northing"],
            }
            for p in res.data
            if isinstance(p, dict)
        ]
        return Record(
            source_id=self.id,
            kind="profile",
            payload={"samples": samples, "model": "DTM COMB (swissALTI3D)"},
            retrieved_ts=res.retrieved_ts,
            url=PROFILE_URL,
        )

    def height(self, lon: float, lat: float) -> Record:
        # height service wants LV95; convert via pyproj (cheap, exact)
        from bergbot.core.geospatial.crs import to_lv95

        e, n = to_lv95(lon, lat)
        res = self.fetcher.get_json(
            self.id,
            HEIGHT_URL,
            {"easting": round(e, 1), "northing": round(n, 1), "sr": 2056},
            ttl_s=self.ttl_s,
            what="height",
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        return Record(
            source_id=self.id,
            kind="height",
            payload={"height_m": float(res.data["height"])},
            retrieved_ts=res.retrieved_ts,
            url=HEIGHT_URL,
        )

    def canton(self, lon: float, lat: float) -> Record | None:
        params = {
            "geometry": f"{lon:.6f},{lat:.6f}",
            "geometryType": "esriGeometryPoint",
            "layers": "all:ch.swisstopo.swissboundaries3d-kanton-flaeche.fill",
            "tolerance": 0,
            "sr": 4326,
            "returnGeometry": "false",
        }
        res = self.fetcher.get_json(self.id, IDENTIFY_URL, params, ttl_s=30 * 86400, what="canton lookup")
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        results = res.data.get("results", [])
        if not results:
            return None
        a = results[0].get("attributes", {})
        return Record(
            source_id=self.id,
            kind="canton",
            payload={"code": str(a.get("ak", "")).lower(), "name": a.get("name")},
            retrieved_ts=res.retrieved_ts,
        )


def _box(s: str | None) -> tuple[float, float, float, float] | None:
    if not s:
        return None
    m = re.match(r"BOX\(([-\d.]+) ([-\d.]+),([-\d.]+) ([-\d.]+)\)", s)
    if not m:
        return None
    x1, y1, x2, y2 = (float(v) for v in m.groups())
    return (x1, y1, x2, y2)


def now() -> datetime:
    return datetime.now(tz=UTC)
