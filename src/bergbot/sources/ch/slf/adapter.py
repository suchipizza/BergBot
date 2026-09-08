"""SLF CAAML JSON bulletin (aws.slf.ch/api/bulletin/caaml/<lang>/json). Out of season the list is empty.
Query kind `bulletin`: bbox point → the bulletin whose region polygon contains the point (if any).
Phase 1 reports presence and level only; no interpretation for hiking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.http import Fetcher, default_fetcher

BULLETIN_URL = "https://aws.slf.ch/api/bulletin/caaml/{lang}/json"
REGIONS_URL = "https://aws.slf.ch/api/bulletin/caaml/{lang}/geojson"


class SLFAdapter:
    id = "ch.slf"
    kinds: ClassVar[tuple[str, ...]] = ("bulletin",)
    ttl_s: ClassVar[int] = 3600

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None
        self._latency: int | None = None

    def fetch(self, query: Query) -> list[Record]:
        lang = str(query.params.get("lang", "en"))
        bulletins = self.bulletins(lang)
        if not query.bbox:
            return bulletins
        lon, lat = query.bbox[0], query.bbox[1]
        return [b for b in bulletins if _contains(b.payload.get("region_polygons") or [], lon, lat)]

    def bulletins(self, lang: str = "en") -> list[Record]:
        res = self.fetcher.get_json(
            self.id, BULLETIN_URL.format(lang=lang), None, ttl_s=self.ttl_s, what="SLF bulletin"
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        out: list[Record] = []
        for b in res.data.get("bulletins", []):
            ratings = b.get("dangerRatings") or []
            levels: list[int] = [lv for lv in (_level(r.get("mainValue")) for r in ratings) if lv is not None]
            out.append(
                Record(
                    source_id=self.id,
                    kind="bulletin",
                    payload={
                        "bulletin_id": b.get("bulletinID"),
                        "valid_start": (b.get("validTime") or {}).get("startTime"),
                        "valid_end": (b.get("validTime") or {}).get("endTime"),
                        "regions": [r.get("name") for r in b.get("regions") or []],
                        "region_ids": [r.get("regionID") for r in b.get("regions") or []],
                        "region_polygons": [],
                        "level_max": max(levels) if levels else None,
                        "levels": levels,
                        "highlights": b.get("highlights"),
                    },
                    source_ts=_ts(b.get("publicationTime")),
                    retrieved_ts=res.retrieved_ts,
                    url="https://www.slf.ch/en/avalanche-bulletin-and-snow-situation.html",
                    original_span=" ".join(str(b.get("highlights") or "").split()[:15]) or None,
                )
            )
        return out

    def freshness(self) -> Freshness:
        return Freshness(source_ts=self._last, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return Licence(
            name="SLF bulletin terms (free use with attribution; no interpretation claims)",
            redistribution=False,
            attribution="© SLF",
            url="https://www.slf.ch/en/avalanche-bulletin-and-snow-situation.html",
        )

    def health(self) -> Health:
        try:
            self.bulletins("en")
            return Health(
                ok=True,
                latency_ms=self._latency,
                last_success_ts=self._last,
                note="reachable (empty out of season)",
            )
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))


def _level(v: Any) -> int | None:
    m = {"low": 1, "moderate": 2, "considerable": 3, "high": 4, "very_high": 5}
    if isinstance(v, int):
        return v
    return m.get(str(v).lower()) if v else None


def _ts(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def _contains(polys: list[Any], lon: float, lat: float) -> bool:
    if not polys:
        return False
    from shapely.geometry import Point, shape

    p = Point(lon, lat)
    return any(shape(g).contains(p) for g in polys)


def now() -> datetime:
    return datetime.now(tz=UTC)
