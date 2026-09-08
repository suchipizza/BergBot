"""Layer `ch.astra.wanderland-sperrungen_umleitungen`: closed segments and diversions, with reason and duration
in four languages. Live per audit (no cache beyond 1 h) — closures change daily."""

from __future__ import annotations

from typing import Any, ClassVar

from bergbot.sources.base import Query, Record
from bergbot.sources.geoadmin_base import GeoAdminLayerAdapter


class ClosuresAdapter(GeoAdminLayerAdapter):
    id = "ch.closures"
    kinds: ClassVar[tuple[str, ...]] = ("closures",)
    layers: ClassVar[tuple[str, ...]] = ("ch.astra.wanderland-sperrungen_umleitungen",)
    ttl_s = 3600
    record_kind = "closure"
    attribution: ClassVar[str] = "© ASTRA / SchweizMobil"

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        rec.payload["closure_type"] = a.get("sperrungen_type")  # "closed" | "detour" | ...
        rec.payload["is_detour"] = a.get("sperrungen_type") == "detour"
        rec.payload["reason"] = {lang: a.get(f"reason_{lang}") for lang in ("de", "fr", "it", "en")}
        rec.payload["duration"] = {lang: a.get(f"duration_{lang}") for lang in ("de", "fr", "it", "en")}
        rec.payload["type_label"] = {
            lang: a.get(f"sperrungen_type_{lang}") for lang in ("de", "fr", "it", "en")
        }
        span = a.get("reason_de") or a.get("sperrungen_type_de") or ""
        rec.original_span = " ".join(str(span).split()[:15]) or None
        rec.url = "https://schweizmobil.ch/en/hiking-in-switzerland/closures"
        return rec
