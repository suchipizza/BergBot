"""Layer `ch.vbs.schiessanzeigen`: danger zones of published firing notices with weekdays (`wochentag`, 1=Mon…7=Sun)
and links to the notice page (armee.ch/schiessanzeigen/<id>) which lists dates and times. The layer does not carry
exact dates, so a zone intersecting the route yields `shooting_zone` with a web-verification spec to confirm the
schedule for the date (`shooting_activity` once verified). Live per audit (1 h cache)."""

from __future__ import annotations

from typing import Any, ClassVar

from bergbot.sources.base import Licence, Query, Record
from bergbot.sources.geoadmin_base import GeoAdminLayerAdapter


class ArmyShootingAdapter(GeoAdminLayerAdapter):
    id = "ch.army"
    kinds: ClassVar[tuple[str, ...]] = ("shooting_zones",)
    layers: ClassVar[tuple[str, ...]] = ("ch.vbs.schiessanzeigen",)
    ttl_s = 3600
    record_kind = "shooting_zone"
    licence_obj: ClassVar[Licence] = Licence(name="OGD (VBS)", redistribution=True, attribution="© VBS")
    health_bbox = (7.5, 46.5, 8.5, 47.0)

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        rec.payload["name"] = a.get("bezeichnung")
        rec.payload["place"] = a.get("bezeichnung_ort")
        rec.payload["weekdays"] = a.get("wochentag") or []
        rec.payload["notice_id"] = a.get("belplan_id")
        rec.payload["info_phone"] = a.get("infotelefonnr")
        rec.payload["urls"] = {lang: a.get(f"url_{lang}") for lang in ("de", "fr", "it", "en")}
        rec.url = a.get("url_en") or a.get("url_de")
        rec.original_span = " ".join(str(a.get("bezeichnung_ort") or "").split()[:15]) or None
        return rec
