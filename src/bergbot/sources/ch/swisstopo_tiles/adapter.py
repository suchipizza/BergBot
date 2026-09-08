"""Fetch and stitch swisstopo `pixelkarte-farbe` tiles (EPSG:3857) for a bbox into one JPEG (≤ 400 KB target).
Decision 002. Returned as bytes + the pixel↔lon/lat transform so the SVG route can be overlaid exactly."""

from __future__ import annotations

import io
import math
from datetime import UTC, datetime
from typing import Any, ClassVar

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.http import Fetcher, default_fetcher

TILE_URL = (
    "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/{z}/{x}/{y}.jpeg"
)
TILE = 256


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 2**z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2.0 * n
    return x, y


def choose_zoom(bbox: tuple[float, float, float, float], max_px: int = 1024) -> int:
    for z in range(16, 9, -1):
        x0, y0 = lonlat_to_tile(bbox[0], bbox[3], z)
        x1, y1 = lonlat_to_tile(bbox[2], bbox[1], z)
        if (x1 - x0) * TILE <= max_px and (y1 - y0) * TILE <= max_px:
            return z
    return 10


class SwisstopoTilesAdapter:
    id = "ch.swisstopo_tiles"
    kinds: ClassVar[tuple[str, ...]] = ("map",)
    ttl_s: ClassVar[int] = 30 * 86400

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None

    def fetch(self, query: Query) -> list[Record]:
        if not query.bbox:
            raise ValueError("map needs bbox")
        return [
            self.stitch(
                query.bbox,
                max_px=int(query.params.get("max_px", 1024)),
                quality=int(query.params.get("quality", 70)),
            )
        ]

    def stitch(
        self, bbox: tuple[float, float, float, float], max_px: int = 1024, quality: int = 70
    ) -> Record:
        from PIL import Image

        z = choose_zoom(bbox, max_px)
        fx0, fy0 = lonlat_to_tile(bbox[0], bbox[3], z)
        fx1, fy1 = lonlat_to_tile(bbox[2], bbox[1], z)
        tx0, ty0, tx1, ty1 = int(fx0), int(fy0), int(fx1), int(fy1)
        w, h = (tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE
        canvas = Image.new("RGB", (w, h), (235, 235, 235))
        fetched = 0
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                url = TILE_URL.format(z=z, x=tx, y=ty)
                try:
                    res = self.fetcher.get_bytes(self.id, url, ttl_s=self.ttl_s, what=f"tile {z}/{tx}/{ty}")
                except SourceUnavailable:
                    continue
                if res.raw:
                    canvas.paste(
                        Image.open(io.BytesIO(res.raw)).convert("RGB"), ((tx - tx0) * TILE, (ty - ty0) * TILE)
                    )
                    fetched += 1
                    self._last = res.retrieved_ts
        if fetched == 0:
            raise SourceUnavailable(self.id, "map tiles")
        # crop to the exact bbox
        left, top = int((fx0 - tx0) * TILE), int((fy0 - ty0) * TILE)
        right, bottom = int((fx1 - tx0) * TILE), int((fy1 - ty0) * TILE)
        canvas = canvas.crop((left, top, max(right, left + 1), max(bottom, top + 1)))
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        # shrink until ≤ 400 KB
        q = quality
        while len(data) > 400_000 and q > 35:
            q -= 10
            buf = io.BytesIO()
            canvas.save(buf, format="JPEG", quality=q, optimize=True)
            data = buf.getvalue()
        payload: dict[str, Any] = {
            "jpeg": data,
            "width": canvas.width,
            "height": canvas.height,
            "zoom": z,
            "bbox": bbox,
            "attribution": "© swisstopo",
            "tiles": fetched,
        }
        return Record(
            source_id=self.id,
            kind="map",
            payload=payload,
            retrieved_ts=self._last or datetime.now(tz=UTC),
            url="https://map.geo.admin.ch",
        )

    def freshness(self) -> Freshness:
        return Freshness(source_ts=None, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return Licence(
            name="OGD swisstopo (free use with attribution since 2021)",
            redistribution=True,
            attribution="© swisstopo",
            url="https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices",
        )

    def health(self) -> Health:
        try:
            self.fetcher.get_bytes(
                self.id, TILE_URL.format(z=14, x=8580, y=5740), ttl_s=self.ttl_s, what="probe tile"
            )
            return Health(ok=True, last_success_ts=self._last)
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))
