"""Two GeoAdmin layers:
- `ch.swisstopo.swisstlm3d-wanderwege`: every official hiking trail segment (geometry, hikingtype null/1/2/3 ≈ T1/T2-3/T4+).
- `ch.astra.wanderland`: named SwitzerlandMobility routes (national/regional/local) with their segments.
Route synthesis in core/routing only ever assembles segments from these layers (SR-5)."""

from __future__ import annotations

from typing import Any, ClassVar

from bergbot.sources.base import Query, Record
from bergbot.sources.geoadmin_base import GeoAdminLayerAdapter

HIKINGTYPE_TO_GRADE = {
    None: None,
    0: "T1",
    1: "T1",
    2: "T2",
    3: "T4",
}  # swissTLM3D: 1 Wanderweg, 2 Bergwanderweg, 3 Alpinwanderweg


class HikingNetworkAdapter(GeoAdminLayerAdapter):
    id = "ch.hiking_network"
    kinds: ClassVar[tuple[str, ...]] = ("trails",)
    layers: ClassVar[tuple[str, ...]] = ("ch.swisstopo.swisstlm3d-wanderwege",)
    ttl_s = 30 * 86400
    record_kind = "trail_segment"
    limit = 500

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        ht = rec.payload["attributes"].get("hikingtype")
        rec.payload["grade_hint"] = HIKINGTYPE_TO_GRADE.get(ht)
        rec.payload["network"] = "ch.swisstopo.swisstlm3d-wanderwege"
        return rec


class WanderlandRoutesAdapter(GeoAdminLayerAdapter):
    id = "ch.hiking_network.wanderland"
    kinds: ClassVar[tuple[str, ...]] = ("routes",)
    layers: ClassVar[tuple[str, ...]] = ("ch.astra.wanderland",)
    ttl_s = 30 * 86400
    record_kind = "named_route"
    limit = 100
    attribution: ClassVar[str] = "© SchweizMobil / ASTRA"

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        num = a.get("chmobil_route_number")
        rec.payload["name"] = a.get("chmobil_title")
        rec.payload["route_number"] = num
        rec.payload["network"] = "ch.astra.wanderland"
        # 1–2 digits national/regional, 3 digits local
        rec.payload["prominence"] = (
            "national" if num and num < 10 else "regional" if num and num < 100 else "local"
        )
        rec.url = f"https://schweizmobil.ch/en/hiking-in-switzerland/route-{num}" if num else rec.url
        return rec
