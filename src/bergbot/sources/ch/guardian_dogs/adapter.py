"""Layer `ch.bafu.alpweiden-herdenschutzhunde`: pastures where guardian dogs are present in season, with contact
and a link to protectiondestroupeaux.ch. Cached 7 days (presence changes with the alp season)."""

from __future__ import annotations

from typing import Any, ClassVar

from bergbot.sources.base import Licence, Query, Record
from bergbot.sources.geoadmin_base import GeoAdminLayerAdapter


class GuardianDogsAdapter(GeoAdminLayerAdapter):
    id = "ch.guardian_dogs"
    kinds: ClassVar[tuple[str, ...]] = ("guardian_dogs",)
    layers: ClassVar[tuple[str, ...]] = ("ch.bafu.alpweiden-herdenschutzhunde",)
    ttl_s = 7 * 86400
    record_kind = "guardian_dog_area"
    licence_obj: ClassVar[Licence] = Licence(
        name="OGD (BAFU / AGRIDEA)", redistribution=True, attribution="© BAFU / AGRIDEA"
    )
    health_bbox = (9.0, 46.5, 10.0, 47.0)

    def normalise(self, feature: dict[str, Any], query: Query) -> Record:
        rec = super().normalise(feature, query)
        a = rec.payload["attributes"]
        rec.payload["name"] = a.get("name") or a.get("label")
        rec.payload["contact"] = a.get("kontname")
        rec.payload["phone"] = a.get("konttel")
        rec.payload["info_url"] = a.get("refmeldungbeweidungszone")
        rec.url = a.get("refmeldungbeweidungszone") or "https://www.protectiondestroupeaux.ch"
        return rec
