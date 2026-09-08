from __future__ import annotations

from bergbot.core.domain import Amenity, AmenityStatus, Evidence, EvidenceClass, EvidenceSummary, Warning

CHECK_LABELS = {
    "ch.geoadmin": "geometry_elevation",
    "ch.hiking_network": "network_membership",
    "ch.hiking_network.wanderland": "route_identity",
    "ch.closures": "closures",
    "ch.meteoswiss": "weather_wind",
    "ch.bafu.fire": "fire_danger",
    "ch.bafu.quiet_zones": "wildlife_quiet_zones",
    "ch.bafu.protected_areas": "protected_areas",
    "ch.guardian_dogs": "guardian_dogs",
    "ch.army": "shooting_zones",
    "ch.transport": "public_transport",
    "ch.slf": "avalanche_bulletin",
    "shared.osm": "huts_water_lifts",
}


def summarise(
    evidence: list[Evidence], warnings: list[Warning], amenities: list[Amenity], unavailable: list[str]
) -> EvidenceSummary:
    s = EvidenceSummary()
    all_ev = list(evidence) + [e for w in warnings for e in w.evidence]
    sources = {e.source for e in all_ev}
    for src in sorted(sources):
        label = CHECK_LABELS.get(src, src)
        if label not in s.checked:
            s.checked.append(label)
    for e in all_ev:
        text = e.translated_summary or e.original_span or e.source
        if e.cls in (EvidenceClass.A, EvidenceClass.B) and e.verification != "unverified":
            _add(s.known, text)
        elif e.cls is EvidenceClass.D:
            _add(s.inferred, text)
        elif e.cls is EvidenceClass.C:
            _add(s.uncertain, text)
    for a in amenities:
        if a.kind.value in ("hut", "lift") and a.status is AmenityStatus.unverified:
            _add(s.unverified, f"{a.kind.value}:{a.name}")
    for u in sorted(set(unavailable)):
        _add(s.unverified, CHECK_LABELS.get(u, u))
    return s


def _add(lst: list[str], text: str) -> None:
    if text not in lst:
        lst.append(text)
