"""BAFU layers on GeoAdmin.

- QuietZonesAdapter   ch.bafu.wrz-wildruhezonen_portal  (name, rule code R10/R20/R30, protection period, legal status)
- ProtectedAreasAdapter  parks, federal hunting reserves, mire landscapes, Ramsar (static, 30 d)
- FireDangerAdapter   ch.bafu.gefahren-waldbrand_warnung (danger level by region, valid_from) and
                      ch.bafu.gefahren-waldbrand_praeventionsmassnahmen_kantone (cantonal measures: fire bans)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, ClassVar

from bergbot.sources.base import Licence, Query, Record
from bergbot.sources.geoadmin_base import GeoAdminLayerAdapter

BAFU_LICENCE = Licence(
    name="OGD (BAFU)",
    redistribution=True,
    attribution="© BAFU",
    url="https://www.bafu.admin.ch/bafu/en/home/state/data/geodata.html",
)

# Danger level from the DE title; the layer carries text, not a number.
_LEVEL_WORDS = {
    "keine": 0,
    "gering": 1,
    "mässig": 2,
    "maessig": 2,
    "erheblich": 3,
    "gross": 4,
    "sehr gross": 5,
}


def level_from_title(title_de: str | None) -> int | None:
    if not title_de:
        return None
    t = title_de.lower()
    if "sehr gross" in t:
        return 5
    for w, lvl in _LEVEL_WORDS.items():
        if w in t:
            return lvl
    return None


class QuietZonesAdapter(GeoAdminLayerAdapter):
    id = "ch.bafu.quiet_zones"
    kinds: ClassVar[tuple[str, ...]] = ("quiet_zones",)
    layers: ClassVar[tuple[str, ...]] = ("ch.bafu.wrz-wildruhezonen_portal",)
    ttl_s = 30 * 86400
    record_kind = "quiet_zone"
    licence_obj: ClassVar[Licence] = BAFU_LICENCE
    health_bbox = (9.5, 46.5, 10.0, 47.0)

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        rec.payload["name"] = a.get("wrz_name")
        rec.payload["rule_code"] = a.get("bestimmung")
        rec.payload["rule"] = {lang: a.get(f"best_{lang}") for lang in ("de", "fr", "it")}
        rec.payload["period"] = a.get("schutzzeit")
        rec.payload["binding"] = a.get("schutzs_de") == "rechtsverbindlich"
        rec.original_span = " ".join(str(a.get("best_de") or "").split()[:15]) or None
        rec.url = "https://www.wildruhezonen.ch"
        return rec


class ProtectedAreasAdapter(GeoAdminLayerAdapter):
    id = "ch.bafu.protected_areas"
    kinds: ClassVar[tuple[str, ...]] = ("protected_areas",)
    layers: ClassVar[tuple[str, ...]] = (
        "ch.bafu.schutzgebiete-paerke_nationaler_bedeutung",
        "ch.bafu.schutzgebiete-aulav_jagdbanngebiete",
        "ch.bafu.bundesinventare-moorlandschaften",
        "ch.bafu.schutzgebiete-ramsar",
    )
    ttl_s = 30 * 86400
    record_kind = "protected_area"
    licence_obj: ClassVar[Licence] = BAFU_LICENCE
    health_bbox = (10.1, 46.6, 10.3, 46.7)

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        layer = rec.payload["layer"] or ""
        kind = {
            "paerke": "park",
            "jagdbann": "hunting_reserve",
            "moorlandschaften": "mire_landscape",
            "ramsar": "ramsar",
        }
        rec.payload["area_kind"] = next((v for k, v in kind.items() if k in layer), "protected")
        rec.payload["name"] = a.get("name") or a.get("key_name") or a.get("label")
        rec.payload["zone"] = a.get("zone") or a.get("typ")
        return rec


class FireDangerAdapter(GeoAdminLayerAdapter):
    id = "ch.bafu.fire"
    kinds: ClassVar[tuple[str, ...]] = ("fire_danger",)
    layers: ClassVar[tuple[str, ...]] = (
        "ch.bafu.gefahren-waldbrand_warnung",
        "ch.bafu.gefahren-waldbrand_praeventionsmassnahmen_kantone",
    )
    ttl_s = 3600
    record_kind = "fire"
    return_geometry = False
    licence_obj: ClassVar[Licence] = BAFU_LICENCE
    health_bbox = (8.9, 46.1, 9.0, 46.2)

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        layer = rec.payload["layer"] or ""
        rec.payload["region"] = {lang: a.get(f"name_{lang}") for lang in ("de", "fr", "it", "en")}
        rec.payload["title"] = {lang: a.get(f"title_{lang}") for lang in ("de", "fr", "it", "en")}
        rec.payload["canton"] = (a.get("canton") or "").lower() or None
        if "warnung" in layer:
            rec.kind = "fire_danger"
            rec.payload["level"] = level_from_title(a.get("title_de"))
            rec.url = "https://www.waldbrandgefahr.ch"
        else:
            rec.kind = "fire_measures"
            rec.payload["description"] = {
                lang: a.get(f"description_{lang}") for lang in ("de", "fr", "it", "en")
            }
            title_de = (a.get("title_de") or "").lower()
            rec.payload["ban"] = "verbot" in title_de or "keine massnahmen" not in title_de and bool(title_de)
            rec.payload["no_measures"] = "keine massnahmen" in title_de
            rec.url = "https://www.waldbrandgefahr.ch"
        rec.source_ts = _parse_valid_from(a.get("valid_from"))
        rec.original_span = " ".join(str(a.get("title_de") or "").split()[:15]) or None
        return rec


def _parse_valid_from(v: str | None) -> datetime | None:
    if not v:
        return None
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", v)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    return datetime(y, mo, d, tzinfo=UTC)
