"""Shared machinery for adapters backed by GeoAdmin (api3.geo.admin.ch) layers.

The identify endpoint answers "which features of layer X intersect this envelope / geometry". Each adapter
names its layers, its TTL and how to normalise attributes. Geometry comes back as GeoJSON in WGS84.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, ClassVar

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.http import Fetcher, default_fetcher

IDENTIFY_URL = "https://api3.geo.admin.ch/rest/services/all/MapServer/identify"
SEARCH_URL = "https://api3.geo.admin.ch/rest/services/api/SearchServer"
PROFILE_URL = "https://api3.geo.admin.ch/rest/services/profile.json"
HEIGHT_URL = "https://api3.geo.admin.ch/rest/services/height"

OGD_LICENCE = Licence(
    name="OGD (opendata.swiss: open use, source must be provided)",
    redistribution=True,
    attribution="© swisstopo",
    url="https://www.geo.admin.ch/en/general-terms-of-use-fsdi",
)


def bbox_str(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(f"{v:.6f}" for v in bbox)


class GeoAdminLayerAdapter:
    """Base: `fetch(Query(kind=..., bbox=...|geometry=...))` → one Record per feature."""

    id: str = "ch.geoadmin.layer"
    kinds: ClassVar[tuple[str, ...]] = ()
    layers: ClassVar[tuple[str, ...]] = ()
    ttl_s: ClassVar[int] = 0
    record_kind: ClassVar[str] = "feature"
    return_geometry: ClassVar[bool] = True
    limit: ClassVar[int] = 200
    attribution: ClassVar[str] = "© swisstopo"
    licence_obj: ClassVar[Licence] = OGD_LICENCE
    health_bbox: ClassVar[tuple[float, float, float, float]] = (8.55, 46.95, 8.70, 47.05)  # Brunnen area

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None
        self._last_latency: int | None = None
        self._last_from_cache = False

    # -- contract --
    def fetch(self, query: Query) -> list[Record]:
        features = self.identify(query)
        return [self.normalise(f, query) for f in features]

    def freshness(self) -> Freshness:
        return Freshness(source_ts=None, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return self.licence_obj

    def health(self) -> Health:
        try:
            t = self.identify(
                Query(kind=self.kinds[0] if self.kinds else "health", bbox=self.health_bbox), limit=1
            )
            return Health(
                ok=True,
                latency_ms=self._last_latency,
                last_success_ts=self._last,
                note=f"{len(t)} feature(s) in probe bbox",
            )
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))

    # -- helpers --
    def identify(self, query: Query, limit: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "layers": "all:" + ",".join(self.layers),
            "tolerance": 0,
            "sr": 4326,
            "returnGeometry": "true" if self.return_geometry else "false",
            "geometryFormat": "geojson",
            "limit": limit or self.limit,
        }
        if query.geometry is not None:
            params["geometry"] = json.dumps(query.geometry, separators=(",", ":"))
            params["geometryType"] = (
                "esriGeometryPolyline"
                if query.geometry.get("type") == "LineString"
                else "esriGeometryPolygon"
            )
        elif query.bbox is not None:
            params["geometry"] = bbox_str(query.bbox)
            params["geometryType"] = "esriGeometryEnvelope"
        else:
            raise ValueError(f"{self.id}: query needs bbox or geometry")
        res = self.fetcher.get_json(
            self.id,
            IDENTIFY_URL,
            params,
            ttl_s=self.ttl_s,
            what=f"{self.layers} for {params['geometry'][:40]}",
        )
        self._last = res.retrieved_ts
        self._last_latency = res.latency_ms
        self._last_from_cache = res.from_cache
        results = res.data.get("results", []) if isinstance(res.data, dict) else []
        return list(results)

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        attrs = dict(feature.get("attributes") or feature.get("properties") or {})
        return Record(
            source_id=self.id,
            kind=self.record_kind,
            payload={
                "layer": feature.get("layerBodId"),
                "feature_id": str(feature.get("featureId") or feature.get("id")),
                "attributes": attrs,
                "geometry": feature.get("geometry"),
                "bbox": feature.get("bbox"),
            },
            source_ts=self.source_ts(attrs),
            retrieved_ts=self._last or datetime.now(tz=UTC),
            url=self.feature_url(feature, attrs),
        )

    def source_ts(self, attrs: dict[str, Any]) -> datetime | None:
        return None

    def feature_url(self, feature: dict[str, Any], attrs: dict[str, Any]) -> str | None:
        return f"https://map.geo.admin.ch/?layers={feature.get('layerBodId')}"
