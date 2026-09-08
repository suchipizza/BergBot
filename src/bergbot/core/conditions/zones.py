"""Spatial intersections of the route with official layers → warnings with km ranges (evidence A + B).
Severity policy (documented, class D):
- trail_closure (closed) critical · diversion important
- shooting_zone important (+ web spec to confirm the day; becomes shooting_activity critical if the weekday is
  listed and the notice cannot be checked, we still keep 'zone' — never infer 'no shooting' from silence)
- wildlife_quiet_zone important when the date falls in the protection period, note otherwise
- protected_area note · guardian_dogs important
"""

from __future__ import annotations

import re
from datetime import date as _date
from typing import Any

from bergbot.core.domain import (
    Evidence,
    EvidenceClass,
    Route,
    Segment,
    SegmentKind,
    Severity,
    Warning,
    WarningType,
)
from bergbot.core.geospatial.ops import intersect_segments, route_bbox
from bergbot.sources.base import Query, Record, SourceUnavailable
from bergbot.sources.ch.army import ArmyShootingAdapter
from bergbot.sources.ch.bafu import ProtectedAreasAdapter, QuietZonesAdapter
from bergbot.sources.ch.closures import ClosuresAdapter
from bergbot.sources.ch.guardian_dogs import GuardianDogsAdapter
from bergbot.sources.geoadmin_base import GeoAdminLayerAdapter
from bergbot.sources.http import Fetcher
from bergbot.sources.shared.web import verification_spec

Prefetched = dict[str, list[Record] | None]


def prefetch_zone_layers(
    bbox: tuple[float, float, float, float], fetcher: Fetcher | None, offline: bool = False
) -> Prefetched:
    """Fetch every zone layer once for a search area so many candidate audits share the records.
    A `None` value marks a source that could not be reached."""
    out: Prefetched = {}
    layers: list[tuple[type[GeoAdminLayerAdapter], str, bool]] = [
        (ClosuresAdapter, "closures", False),
        (ArmyShootingAdapter, "shooting_zones", False),
        (QuietZonesAdapter, "quiet_zones", True),
        (ProtectedAreasAdapter, "protected_areas", True),
        (GuardianDogsAdapter, "guardian_dogs", True),
    ]
    for cls, kind, static in layers:
        if offline and not static:
            out[cls.id] = None
            continue
        try:
            out[cls.id] = list(cls(fetcher).fetch(Query(kind=kind, bbox=bbox)))
        except SourceUnavailable:
            out[cls.id] = None
    return out


def zone_warnings(
    route: Route,
    date: str,
    fetcher: Fetcher | None = None,
    offline: bool = False,
    lang: str = "en",
    prefetched: Prefetched | None = None,
) -> tuple[list[Warning], list[dict[str, Any]], list[str], list[Segment]]:
    """Returns (warnings, zones touched, unavailable sources, route segments to colour)."""
    bbox = route_bbox(route.coords, pad_m=100)
    warnings: list[Warning] = []
    zones: list[dict[str, Any]] = []
    unavailable: list[str] = []
    segments: list[Segment] = []
    weekday = _date.fromisoformat(date).isoweekday()

    def run(adapter_cls: type[GeoAdminLayerAdapter], kind: str, static: bool) -> list[Record]:
        if prefetched is not None and adapter_cls.id in prefetched:
            recs = prefetched[adapter_cls.id]
            if recs is None:
                unavailable.append(adapter_cls.id)
                return []
            return recs
        if offline and not static:
            unavailable.append(adapter_cls.id)
            return []
        try:
            return list(adapter_cls(fetcher).fetch(Query(kind=kind, bbox=bbox)))
        except SourceUnavailable:
            unavailable.append(adapter_cls.id)
            return []

    # closures (live)
    for r in run(ClosuresAdapter, "closures", static=False):
        segs = intersect_segments(
            route.coords,
            r.payload["geometry"],
            buffer_m=20.0,
            kind=SegmentKind.closure,
            label=r.payload.get("closure_type"),
        )
        if not segs:
            continue
        is_detour = bool(r.payload.get("is_detour"))
        ev = _ev(
            r,
            EvidenceClass.A,
            (r.payload.get("reason") or {}).get(lang) or (r.payload.get("reason") or {}).get("en"),
            "de",
        )
        for s in segs:
            segments.append(s)
            warnings.append(
                Warning(
                    type=WarningType.diversion if is_detour else WarningType.trail_closure,
                    severity=Severity.important if is_detour else Severity.critical,
                    evidence=[
                        ev,
                        _derived(
                            f"route intersects closure feature {r.payload.get('feature_id')} for {round((s.to_km - s.from_km) * 1000)} m",
                            r,
                        ),
                    ],
                    affected_segment=s,
                    params={
                        "from_km": s.from_km,
                        "to_km": s.to_km,
                        "source": "SchweizMobil / " + ((r.payload.get("duration") or {}).get(lang) or ""),
                    },
                    original_text=(r.payload.get("reason") or {}).get("de"),
                    original_lang="de",
                )
            )
        zones.append(
            {
                "kind": "closure",
                "id": r.payload.get("feature_id"),
                "type": r.payload.get("closure_type"),
                "reason": r.payload.get("reason"),
                "duration": r.payload.get("duration"),
            }
        )

    # shooting zones (live)
    for r in run(ArmyShootingAdapter, "shooting_zones", static=False):
        segs = intersect_segments(
            route.coords, r.payload["geometry"], kind=SegmentKind.zone, label="shooting"
        )
        if not segs:
            continue
        days = r.payload.get("weekdays") or []
        ev = _ev(r, EvidenceClass.A, f"firing zone {r.payload.get('name')} — {r.payload.get('place')}", "de")
        s = segs[0]
        segments.extend(segs)
        spec = verification_spec(
            "shooting_schedule",
            subject=str(r.payload.get("name")),
            name=str(r.payload.get("name")),
            date=date,
            notice_id=str(r.payload.get("notice_id")),
        )
        warnings.append(
            Warning(
                type=WarningType.shooting_zone,
                severity=Severity.important if (not days or weekday in days) else Severity.note,
                evidence=[ev, _derived(f"route crosses the zone between km {s.from_km} and {s.to_km}", r)],
                affected_segment=s,
                params={
                    "name": r.payload.get("name"),
                    "from_km": s.from_km,
                    "to_km": s.to_km,
                    "date": date,
                    "weekdays": days,
                    "web_verification": spec,
                    "notice_url": r.url,
                },
            )
        )
        zones.append({"kind": "shooting", "name": r.payload.get("name"), "weekdays": days, "url": r.url})

    # quiet zones (static)
    for r in run(QuietZonesAdapter, "quiet_zones", static=True):
        segs = intersect_segments(
            route.coords, r.payload["geometry"], kind=SegmentKind.zone, label="quiet_zone"
        )
        if not segs:
            continue
        active = _in_period(r.payload.get("period"), date)
        ev = _ev(r, EvidenceClass.A, (r.payload.get("rule") or {}).get(lang if lang != "en" else "de"), "de")
        s = segs[0]
        segments.extend(segs)
        warnings.append(
            Warning(
                type=WarningType.wildlife_quiet_zone,
                severity=Severity.important if active else Severity.note,
                evidence=[
                    ev,
                    _derived(
                        f"route inside quiet zone for {round((s.to_km - s.from_km) * 1000)} m; period {r.payload.get('period')}",
                        r,
                    ),
                ],
                affected_segment=s,
                params={
                    "name": r.payload.get("name"),
                    "from_km": s.from_km,
                    "to_km": s.to_km,
                    "period": r.payload.get("period") or "",
                    "rule_code": r.payload.get("rule_code"),
                    "active": active,
                },
                original_text=(r.payload.get("rule") or {}).get("de"),
                original_lang="de",
            )
        )
        zones.append(
            {
                "kind": "quiet_zone",
                "name": r.payload.get("name"),
                "period": r.payload.get("period"),
                "rule": r.payload.get("rule_code"),
                "active": active,
            }
        )

    # protected areas (static)
    for r in run(ProtectedAreasAdapter, "protected_areas", static=True):
        segs = intersect_segments(
            route.coords, r.payload["geometry"], kind=SegmentKind.zone, label="protected"
        )
        if not segs:
            continue
        s = segs[0]
        ev = _ev(r, EvidenceClass.A, f"{r.payload.get('area_kind')}: {r.payload.get('name')}", None)
        warnings.append(
            Warning(
                type=WarningType.protected_area,
                severity=Severity.note,
                evidence=[
                    ev,
                    _derived(f"route inside {r.payload.get('name')} between km {s.from_km} and {s.to_km}", r),
                ],
                affected_segment=s,
                params={
                    "name": r.payload.get("name"),
                    "kind": r.payload.get("area_kind"),
                    "from_km": s.from_km,
                    "to_km": s.to_km,
                },
            )
        )
        zones.append({"kind": r.payload.get("area_kind"), "name": r.payload.get("name")})

    # guardian dogs (static-ish)
    for r in run(GuardianDogsAdapter, "guardian_dogs", static=True):
        segs = intersect_segments(
            route.coords, r.payload["geometry"], buffer_m=50.0, kind=SegmentKind.zone, label="guardian_dogs"
        )
        if not segs:
            continue
        s = segs[0]
        segments.extend(segs)
        ev = _ev(r, EvidenceClass.A, f"alp with guardian dogs: {r.payload.get('name')}", None)
        warnings.append(
            Warning(
                type=WarningType.guardian_dogs,
                severity=Severity.important,
                evidence=[ev, _derived(f"route passes the alp between km {s.from_km} and {s.to_km}", r)],
                affected_segment=s,
                params={
                    "name": r.payload.get("name"),
                    "from_km": s.from_km,
                    "to_km": s.to_km,
                    "info_url": r.payload.get("info_url"),
                },
            )
        )
        zones.append(
            {"kind": "guardian_dogs", "name": r.payload.get("name"), "url": r.payload.get("info_url")}
        )
    return warnings, zones, unavailable, segments


def _ev(r: Record, cls: EvidenceClass, summary: str | None, original_lang: str | None) -> Evidence:
    return Evidence(
        **{"class": cls},
        source=r.source_id,
        url=r.url,
        source_ts=r.source_ts,
        retrieved_ts=r.retrieved_ts,
        original_span=r.original_span,
        original_lang=original_lang,
        translated_summary=summary,
    )


def _derived(text: str, r: Record) -> Evidence:
    return Evidence(
        **{"class": EvidenceClass.B},
        source="bergbot.core",
        retrieved_ts=r.retrieved_ts,
        translated_summary=text,
    )


def _in_period(period: str | None, date: str) -> bool:
    """'20.12. - 30.04.' style period, wrapping over new year."""
    if not period:
        return True
    m = re.match(r"\s*(\d{1,2})\.(\d{1,2})\.?\s*-\s*(\d{1,2})\.(\d{1,2})\.?", period)
    if not m:
        return True
    d1, m1, d2, m2 = (int(x) for x in m.groups())
    d = _date.fromisoformat(date)
    start = (m1, d1)
    end = (m2, d2)
    cur = (d.month, d.day)
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end
