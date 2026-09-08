"""transport.opendata.ch v1 (Open Data Platform Mobility Switzerland timetable). Live per audit.

Query kinds:
- `stops_near`  bbox point (lon,lat) → nearby stations with distance
- `connection`  params from,to,date,time[,is_arrival_time] → connections
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.http import Fetcher, default_fetcher

BASE = "https://transport.opendata.ch/v1"


class TransportAdapter:
    id = "ch.transport"
    kinds: ClassVar[tuple[str, ...]] = ("stops_near", "connection")
    ttl_s: ClassVar[int] = 900

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None
        self._latency: int | None = None

    def fetch(self, query: Query) -> list[Record]:
        if query.kind == "stops_near":
            if not query.bbox:
                raise ValueError("stops_near needs bbox point")
            return self.stops_near(query.bbox[0], query.bbox[1])
        if query.kind == "connection":
            p = query.params
            return self.connections(
                p["from"],
                p["to"],
                p.get("date") or query.date or "",
                p.get("time", "07:00"),
                bool(p.get("is_arrival_time", False)),
                int(p.get("limit", 4)),
            )
        raise ValueError(query.kind)

    def stops_near(self, lon: float, lat: float) -> list[Record]:
        res = self.fetcher.get_json(
            self.id,
            f"{BASE}/locations",
            {"x": round(lat, 5), "y": round(lon, 5), "type": "station"},
            ttl_s=7 * 86400,
            what="stops near point",
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        out = []
        for s in res.data.get("stations", []):
            if not s.get("id") or not (s.get("coordinate") or {}).get("x"):
                continue
            out.append(
                Record(
                    source_id=self.id,
                    kind="stop",
                    payload={
                        "id": s["id"],
                        "name": s["name"],
                        "lat": s["coordinate"]["x"],
                        "lon": s["coordinate"]["y"],
                        "distance_m": s.get("distance"),
                        "icon": s.get("icon"),
                    },
                    retrieved_ts=res.retrieved_ts,
                    url="https://transport.opendata.ch",
                )
            )
        return out

    def connections(
        self, from_: str, to: str, date: str, time: str, is_arrival_time: bool = False, limit: int = 4
    ) -> list[Record]:
        params: dict[str, Any] = {"from": from_, "to": to, "date": date, "time": time, "limit": limit}
        if is_arrival_time:
            params["isArrivalTime"] = 1
        res = self.fetcher.get_json(
            self.id, f"{BASE}/connections", params, ttl_s=self.ttl_s, what=f"connection {from_} → {to}"
        )
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        out = []
        for c in res.data.get("connections", []):
            out.append(
                Record(
                    source_id=self.id,
                    kind="connection",
                    payload={
                        "from": c["from"]["station"]["name"],
                        "to": c["to"]["station"]["name"],
                        "departure": c["from"]["departure"],
                        "arrival": c["to"]["arrival"],
                        "duration": c.get("duration"),
                        "transfers": c.get("transfers"),
                        "products": c.get("products") or [],
                    },
                    retrieved_ts=res.retrieved_ts,
                    url=f"https://www.sbb.ch/en?from={from_}&to={to}&date={date}&time={time}",
                )
            )
        return out

    def freshness(self) -> Freshness:
        return Freshness(source_ts=self._last, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return Licence(
            name="Open Data Platform Mobility Switzerland via transport.opendata.ch",
            redistribution=True,
            attribution="© opendata.ch / SBB timetable",
            url="https://transport.opendata.ch",
        )

    def health(self) -> Health:
        try:
            r = self.stops_near(8.61, 46.99)
            return Health(ok=bool(r), latency_ms=self._latency, last_success_ts=self._last)
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))


def now() -> datetime:
    return datetime.now(tz=UTC)
