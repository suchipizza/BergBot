"""Deterministic workflows: audit · find · around · check. These are what the CLI `--json` commands and the
standalone agent call. No prose here — only structured facts, warnings, evidence and a register-ready Audit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from bergbot import __version__
from bergbot.core.conditions.weather import assess_conditions
from bergbot.core.conditions.zones import Prefetched, prefetch_zone_layers, zone_warnings
from bergbot.core.domain import (
    Activity,
    Amenity,
    AmenityStatus,
    Audit,
    CandidateSet,
    CheckResult,
    Constraint,
    Evidence,
    EvidenceClass,
    Intent,
    Place,
    PlaceKind,
    Route,
    RouteCandidate,
    Segment,
    SegmentKind,
    Severity,
    Warning,
    WarningType,
)
from bergbot.core.evidence.summary import summarise
from bergbot.core.geospatial.ops import distance_to_route_m, is_loop, merge_segments, resample
from bergbot.core.geospatial.parse import parse_route_file
from bergbot.core.geospatial.places import resolve_place
from bergbot.core.logistics.amenities import nearby_amenities
from bergbot.core.logistics.transport import plan_transport
from bergbot.core.routing.candidates import graph_candidates, named_stage_candidates, radius_for, search_bbox
from bergbot.core.routing.identity import identify
from bergbot.core.scoring.score import hard_filter_reasons, soft_score
from bergbot.core.terrain.profile import build_profile, compute_stats, exposed_segments
from bergbot.i18n import normalise_lang
from bergbot.sources.http import Fetcher
from bergbot.sources.shared.web import verification_spec


def default_date() -> str:
    return (datetime.now(tz=UTC) + timedelta(days=1)).date().isoformat()


def run_audit(
    route_file: Path,
    date: str | None = None,
    start_time: str = "09:00",
    lang: str = "en",
    offline: bool = False,
    name: str | None = None,
    fetcher: Fetcher | None = None,
    origin: str | None = None,
    constraints: Constraint | None = None,
) -> Audit:
    route = parse_route_file(Path(route_file), name=name)
    return audit_route(
        route,
        date=date,
        start_time=start_time,
        lang=lang,
        offline=offline,
        fetcher=fetcher,
        origin=origin,
        constraints=constraints,
    )


def audit_route(
    route: Route,
    date: str | None = None,
    start_time: str = "09:00",
    lang: str = "en",
    offline: bool = False,
    fetcher: Fetcher | None = None,
    origin: str | None = None,
    constraints: Constraint | None = None,
    quick: bool = False,
    prefetched: Prefetched | None = None,
) -> Audit:
    """Full check list (PRD §5.4). `quick=True` skips amenities/transport (used while ranking candidates)."""
    lang_n = normalise_lang(lang)
    date = date or default_date()
    unavailable: list[str] = []
    evidence: list[Evidence] = []
    warnings: list[Warning] = []

    route.geometry = {"type": "LineString", "coordinates": resample(route.coords, 25.0)}
    route.is_loop = route.is_loop or is_loop(route.coords)

    # terrain
    prof = build_profile(route, fetcher, offline=offline)
    if prof.evidence:
        evidence.append(prof.evidence)
    if prof.source == "none":
        unavailable.append("ch.geoadmin")
    route.stats = compute_stats(route, prof)
    exposed = exposed_segments(prof)
    route.segments = merge_segments(exposed)
    for s in exposed:
        warnings.append(
            Warning(
                type=WarningType.exposed_terrain,
                severity=Severity.note,
                evidence=[
                    Evidence(
                        **{"class": EvidenceClass.D},
                        source="bergbot.core.terrain",
                        retrieved_ts=datetime.now(tz=UTC),
                        confidence=0.5,
                        translated_summary=f"heuristic: sustained slope {s.slope_pct}% above 1600 m between km {s.from_km} and {s.to_km}",
                    )
                ],
                affected_segment=s,
                params={"from_km": s.from_km, "to_km": s.to_km, "slope_pct": s.slope_pct},
            )
        )

    # identity (skip when the candidate already comes from the network with a known identity)
    if quick and route.identity.network:
        pass
    elif not offline:
        identity, difficulty, id_ev, id_unavail = identify(route, fetcher)
        route.identity = identity
        if difficulty.grade and not route.difficulty.grade:
            route.difficulty = difficulty
        evidence.extend(id_ev)
        unavailable.extend(id_unavail)
    else:
        unavailable.extend(["ch.hiking_network", "ch.hiking_network.wanderland"])

    # start / end places
    c0, c1 = route.coords[0], route.coords[-1]
    route.start = route.start or Place(
        name=route.start.name if route.start else "start",
        kind=PlaceKind.route_point,
        lon=c0[0],
        lat=c0[1],
        elevation_m=round(prof.ele[0]) if prof.source != "none" else None,
    )
    route.end = route.end or Place(
        name="end",
        kind=PlaceKind.route_point,
        lon=c1[0],
        lat=c1[1],
        elevation_m=round(prof.ele[-1]) if prof.source != "none" else None,
    )

    # zones
    zw, zones, z_unavail, z_segs = zone_warnings(
        route, date, fetcher, offline=offline, lang=lang_n, prefetched=prefetched
    )
    warnings.extend(zw)
    unavailable.extend(z_unavail)
    route.segments = merge_segments(route.segments + z_segs)

    # conditions
    duration = route.stats.duration_min if route.stats else 300
    snap, cw = assess_conditions(
        route, prof, date, start_time, duration, exposed, fetcher, offline=offline, lang=lang_n, quick=quick
    )
    warnings.extend(cw)
    evidence.extend(snap.evidence)
    unavailable.extend(snap.unavailable)

    # difficulty ceiling
    if constraints and constraints.max_grade and route.difficulty.grade:
        from bergbot.core.scoring.score import GRADE_RANK

        if GRADE_RANK.get(route.difficulty.grade, 0) > GRADE_RANK.get(constraints.max_grade, 6):
            warnings.append(
                Warning(
                    type=WarningType.difficulty_above_ceiling,
                    severity=Severity.important,
                    evidence=[
                        Evidence(
                            **{"class": EvidenceClass.B},
                            source="bergbot.core",
                            retrieved_ts=datetime.now(tz=UTC),
                            translated_summary=f"{route.difficulty.grade} > ceiling {constraints.max_grade}",
                        )
                    ],
                    params={"grade": route.difficulty.grade, "ceiling": constraints.max_grade},
                )
            )

    amenities: list[Amenity] = []
    transport = None
    escape: list[Place] = []
    if not quick:
        amenities, aw, a_unavail = nearby_amenities(route, date, fetcher, offline=offline)
        warnings.extend(aw)
        unavailable.extend(a_unavail)
        planned_end = snap.window_end
        transport, tw, escape = plan_transport(
            route.start,
            route.end,
            date,
            start_time,
            planned_end,
            origin or (constraints.origin if constraints else None),
            fetcher,
            offline=offline,
        )
        warnings.extend(tw)
        evidence.extend(transport.evidence)
        if transport.unavailable:
            unavailable.append("ch.transport")
        escape = [p for p in escape][:6]

    for u in sorted(set(unavailable)):
        warnings.append(
            Warning(
                type=WarningType.source_unavailable,
                severity=Severity.note,
                evidence=[
                    Evidence(
                        **{"class": EvidenceClass.E},
                        source=u,
                        retrieved_ts=datetime.now(tz=UTC),
                        verification="unverified",
                        translated_summary=f"{u} could not be reached",
                    )
                ],
                params={"what": _label(u), "source": u},
            )
        )

    audit = Audit(
        route=route,
        date=date,
        start_time=start_time,
        lang=lang_n,
        warnings=warnings,
        conditions=snap,
        transport=transport,
        amenities=amenities,
        escape_points=escape,
        zones=zones,
        evidence=evidence,
        generated_at=datetime.now(tz=UTC),
        offline=offline,
        version=__version__,
    )
    audit.summary = summarise(audit.evidence, audit.warnings, audit.amenities, unavailable)
    return audit


def _label(source_id: str) -> str:
    from bergbot.core.evidence.summary import CHECK_LABELS

    return CHECK_LABELS.get(source_id, source_id).replace("_", " ")


def run_around(
    place_text: str,
    constraints: Constraint,
    lang: str = "en",
    limit: int = 3,
    offline: bool = False,
    fetcher: Fetcher | None = None,
) -> CandidateSet:
    place = resolve_place(place_text, lang=lang, fetcher=fetcher)
    return _candidates(place, constraints, Intent.around, lang, limit, offline, fetcher)


def run_find(
    constraints: Constraint,
    lang: str = "en",
    limit: int = 3,
    offline: bool = False,
    fetcher: Fetcher | None = None,
) -> CandidateSet:
    anchor = constraints.place or constraints.start_place or constraints.region or constraints.origin
    if not anchor:
        raise LookupError("find needs a place, region or origin")
    place = resolve_place(anchor, lang=lang, fetcher=fetcher)
    return _candidates(place, constraints, Intent.find, lang, limit, offline, fetcher)


def _candidates(
    place: Place,
    constraints: Constraint,
    intent: Intent,
    lang: str,
    limit: int,
    offline: bool,
    fetcher: Fetcher | None,
) -> CandidateSet:
    lang_n = normalise_lang(lang)
    date = constraints.date or default_date()
    start_time = constraints.start_time or "09:00"
    bbox = search_bbox(place, radius_for(constraints))
    activity = constraints.activity or Activity.hiking
    routes = named_stage_candidates(bbox, fetcher, activity) if not offline else []
    # nearest routes to the place first — a stage that merely crosses the search box 10 km away ranks last
    proximity = {id(r): distance_to_route_m(r.coords, place.lon, place.lat)[0] for r in routes}
    routes.sort(key=lambda r: (proximity[id(r)], r.name))
    near = [r for r in routes if proximity[id(r)] <= 2500.0]
    if len(near) < limit * 2 and not offline:
        extra = graph_candidates(place, bbox, constraints, fetcher, activity)
        for r in extra:
            proximity[id(r)] = 0.0
        routes = near + extra + [r for r in routes if r not in near]
    routes = routes[: max(limit * 3, 9)]
    unavailable: list[str] = []
    ranked: list[RouteCandidate] = []
    prefetched = prefetch_zone_layers(_routes_bbox(routes, bbox), fetcher, offline=offline)
    for r in routes:
        try:
            a = audit_route(
                r,
                date=date,
                start_time=start_time,
                lang=lang_n,
                offline=offline,
                fetcher=fetcher,
                constraints=constraints,
                quick=True,
                prefetched=prefetched,
            )
        except Exception as e:  # noqa: BLE001 — one bad candidate must not sink the set
            unavailable.append(f"candidate {r.name}: {type(e).__name__}")
            continue
        reasons = hard_filter_reasons(a.route, constraints, a.warnings)
        if reasons:
            continue
        weather = _weather_summary(a)
        score, br = soft_score(a.route, constraints, a.warnings, weather, None, proximity_m=proximity[id(r)])
        ranked.append(
            RouteCandidate(
                route=a.route,
                score=score,
                score_breakdown=br,
                warnings=a.warnings,
                weather_summary=_weather_text(a),
                transport_summary=None,
                why={
                    "weather": weather,
                    "distance_from_place_m": round(proximity[id(r)]),
                    "ascent_m": a.route.stats.ascent_m if a.route.stats else None,
                    "distance_km": a.route.stats.distance_km if a.route.stats else None,
                    "named": a.route.identity.network == "ch.astra.wanderland",
                    "famous": a.route.identity.famous,
                    "max_severity": a.max_severity.value if a.max_severity else None,
                },
            )
        )
    ranked.sort(key=lambda c: (-c.score, c.route.name))
    return CandidateSet(
        intent=intent,
        constraints=constraints,
        place=place,
        candidates=ranked[:limit],
        lang=lang_n,
        unavailable=unavailable,
        generated_at=datetime.now(tz=UTC),
    )


def _routes_bbox(
    routes: list[Route], fallback: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    if not routes:
        return fallback
    lons = [c[0] for r in routes for c in r.coords]
    lats = [c[1] for r in routes for c in r.coords]
    return (min(lons) - 0.002, min(lats) - 0.002, max(lons) + 0.002, max(lats) + 0.002)


def _weather_summary(a: Audit) -> dict[str, float | None]:
    if not a.conditions or not a.conditions.hours:
        return {"precip_mm": None, "gust_kmh": None, "storm": None}
    hs = [h for h in a.conditions.hours if a.conditions.window_start <= h.time <= a.conditions.window_end]
    highest = max((h.elevation_m or 0) for h in hs) if hs else 0
    return {
        "precip_mm": round(sum((h.precip_mm or 0.0) for h in hs if (h.elevation_m or 0) == highest), 1),
        "gust_kmh": max((h.gust_kmh or 0.0) for h in hs) if hs else None,
        "storm": 1.0 if any((h.thunder_prob or 0) >= 50 for h in hs) else 0.0,
    }


def _weather_text(a: Audit) -> str | None:
    if not a.conditions or not a.conditions.hours:
        return None
    hs = [h for h in a.conditions.hours if a.conditions.window_start <= h.time <= a.conditions.window_end]
    if not hs:
        return None
    temps = [h.temp_c for h in hs if h.temp_c is not None]
    codes = [h.summary for h in hs if h.summary]
    main = max(set(codes), key=codes.count) if codes else "unknown"
    return f"{main}|{round(min(temps)) if temps else ''}|{round(max(temps)) if temps else ''}|{round(max((h.gust_kmh or 0) for h in hs))}"


def run_check(
    kind: str, name: str, date: str | None = None, lang: str = "en", fetcher: Fetcher | None = None
) -> CheckResult:
    """Single-status check: returns what the deterministic layers know (little), always `unverified`, plus the
    web-verification spec the LLM must execute. Only a WebVerification result can flip the status."""
    date = date or default_date()
    kind_map = {
        "lift": "lift_status",
        "hut": "hut_open",
        "pass": "pass_open",
        "road": "road_open",
        "fire_ban": "fire_ban",
    }
    st = kind_map.get(kind, kind)
    evidence: list[Evidence] = []
    status = AmenityStatus.unverified
    if st == "fire_ban":
        try:
            place = resolve_place(name, lang=lang, fetcher=fetcher)
            from bergbot.sources.base import Query
            from bergbot.sources.ch.bafu import FireDangerAdapter

            recs = FireDangerAdapter(fetcher).fetch(
                Query(
                    kind="fire_danger",
                    bbox=(place.lon - 0.01, place.lat - 0.01, place.lon + 0.01, place.lat + 0.01),
                )
            )
            for r in recs:
                evidence.append(
                    Evidence(
                        **{"class": EvidenceClass.A},
                        source=r.source_id,
                        url=r.url,
                        source_ts=r.source_ts,
                        retrieved_ts=r.retrieved_ts,
                        original_span=r.original_span,
                        original_lang="de",
                        translated_summary=(r.payload.get("title") or {}).get(normalise_lang(lang)),
                        verification="verified",
                    )
                )
        except Exception:  # noqa: BLE001
            pass
    spec = verification_spec(st, subject=name, name=name, date=date, canton_name=name, region=name)
    return CheckResult(
        kind=kind,
        name=name,
        date=date,
        status=status,
        verification="unverified",
        evidence=evidence,
        web_verification_spec=spec,
        lang=normalise_lang(lang),
        generated_at=datetime.now(tz=UTC),
    )


__all__ = [
    "run_audit",
    "audit_route",
    "run_find",
    "run_around",
    "run_check",
    "default_date",
    "Segment",
    "SegmentKind",
]
