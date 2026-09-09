"""Sample the forecast at three route points (start, highest, end) for every hour of the planned window and
derive condition warnings. Thresholds (documented here, class D interpretation):
- exposed_wind: gust ≥ 50 km/h during the window while an exposed segment exists; ≥ 70 km/h anywhere → important
- thunderstorm: any thunderstorm code within window + 2 h → important
- heavy_precipitation: ≥ 10 mm within window → important; ≥ 4 mm → note
- heat: ≥ 30 °C at the lowest point → note; cold: ≤ 0 °C at the highest point → note
- snow_context: freezing level below route max or snowfall > 0 within window → note
- fire_danger: level ≥ 3 → note, ≥ 4 → important; fire_restriction (cantonal measures) → important (serious)
- avalanche_context: SLF bulletin present → note (presence only, serious register per FR-R2)
- long_day: planned end after sunset → note
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from bergbot.core.domain import (
    ConditionSnapshot,
    Evidence,
    EvidenceClass,
    Route,
    Segment,
    Severity,
    Warning,
    WarningType,
    WeatherHour,
)
from bergbot.core.terrain.profile import ElevationProfile, lonlat_of
from bergbot.sources.base import Query, SourceUnavailable
from bergbot.sources.ch.bafu import FireDangerAdapter
from bergbot.sources.ch.meteoswiss import MeteoSwissAdapter
from bergbot.sources.ch.slf import SLFAdapter
from bergbot.sources.http import Fetcher

ZURICH = "+02:00"
FORECAST_DAYS = 7  # constant so requests (and recorded fixtures) do not depend on today's date


def assess_conditions(
    route: Route,
    prof: ElevationProfile,
    date: str,
    start_time: str,
    duration_min: int,
    exposed: list[Segment],
    fetcher: Fetcher | None = None,
    offline: bool = False,
    lang: str = "en",
    quick: bool = False,
) -> tuple[ConditionSnapshot, list[Warning]]:
    window_start = _local(date, start_time)
    window_end = window_start + timedelta(minutes=duration_min + 30)
    snap = ConditionSnapshot(window_start=window_start, window_end=window_end)
    warnings: list[Warning] = []
    if offline:
        snap.unavailable = ["ch.meteoswiss", "ch.bafu.fire", "ch.slf"]
        return snap, warnings

    samples = _sample_points(prof)
    if quick and samples:
        samples = [max(samples, key=lambda s: s[1])]  # highest point only while ranking
    hours: list[WeatherHour] = []
    sunset: datetime | None = None
    met = MeteoSwissAdapter(fetcher)
    for km, ele, lon, lat in samples:
        try:
            rec = met.forecast(lon, lat, elevation_m=ele, forecast_days=FORECAST_DAYS)
        except SourceUnavailable:
            snap.unavailable.append("ch.meteoswiss")
            break
        ev = Evidence(
            **{"class": EvidenceClass.C},
            source="ch.meteoswiss",
            url=rec.url,
            source_ts=rec.source_ts,
            retrieved_ts=rec.retrieved_ts,
            confidence=0.8,
            translated_summary=rec.payload.get("model"),
        )
        if ev not in snap.evidence:
            snap.evidence.append(ev)
        if sunset is None:
            days = rec.payload.get("days") or []
            sunsets = rec.payload.get("sunset") or []
            if date in days and len(sunsets) > days.index(date):
                sunset = _parse_local(sunsets[days.index(date)])
        for h in rec.payload["hours"]:
            t = _parse_local(h["time"])
            if t < window_start - timedelta(hours=1) or t > window_end + timedelta(hours=2):
                continue
            hours.append(
                WeatherHour(
                    time=t,
                    km=round(km, 1),
                    elevation_m=round(ele),
                    temp_c=h.get("temp_c"),
                    precip_mm=h.get("precip_mm"),
                    precip_prob=h.get("precip_prob"),
                    wind_kmh=h.get("wind_kmh"),
                    gust_kmh=h.get("gust_kmh"),
                    thunder_prob=100.0 if (h.get("code") or 0) >= 95 else None,
                    summary=h.get("summary"),
                )
            )
    snap.hours = sorted(hours, key=lambda x: (x.time, x.km or 0))
    snap.sunset = sunset
    if snap.hours:
        warnings.extend(_weather_warnings(snap, prof, exposed, window_start, window_end))
    if sunset and window_end > sunset:
        warnings.append(
            _w(
                WarningType.long_day,
                Severity.note,
                snap.evidence[:1] or [_derived("sunset")],
                hours=round(duration_min / 60, 1),
                sunset=sunset.strftime("%H:%M"),
            )
        )

    # fire
    try:
        fire = FireDangerAdapter(fetcher).fetch(Query(kind="fire_danger", bbox=_point_bbox(prof)))
        seen_fire: set[tuple[str, str]] = set()
        for r in fire:
            key = (r.kind, str((r.payload.get("region") or {}).get("de")))
            if key in seen_fire:
                continue
            seen_fire.add(key)
            ev = Evidence(
                **{"class": EvidenceClass.A},
                source="ch.bafu.fire",
                url=r.url,
                source_ts=r.source_ts,
                retrieved_ts=r.retrieved_ts,
                original_span=r.original_span,
                original_lang="de",
                translated_summary=(r.payload.get("title") or {}).get(lang)
                or (r.payload.get("title") or {}).get("en"),
            )
            snap.evidence.append(ev)
            if r.kind == "fire_danger":
                lvl = r.payload.get("level")
                snap.fire_danger_level = max(lvl or 0, snap.fire_danger_level or 0) or None
                if lvl is not None and lvl >= 3:
                    warnings.append(
                        _w(
                            WarningType.fire_danger,
                            Severity.important if lvl >= 4 else Severity.note,
                            [ev],
                            level=lvl,
                            label=(r.payload.get("title") or {}).get(lang) or "",
                            source="waldbrandgefahr.ch",
                        )
                    )
            else:
                snap.fire_restrictions.append(
                    {
                        "region": r.payload.get("region"),
                        "title": r.payload.get("title"),
                        "description": r.payload.get("description"),
                        "ban": r.payload.get("ban"),
                    }
                )
                if r.payload.get("ban"):
                    warnings.append(
                        _w(
                            WarningType.fire_restriction,
                            Severity.important,
                            [ev],
                            scope=(r.payload.get("region") or {}).get(lang)
                            or (r.payload.get("region") or {}).get("en")
                            or "",
                            restriction=(r.payload.get("title") or {}).get(lang)
                            or (r.payload.get("title") or {}).get("en")
                            or "",
                            source="waldbrandgefahr.ch",
                        )
                    )
    except SourceUnavailable:
        snap.unavailable.append("ch.bafu.fire")

    # one fire-danger warning per level (regions merged), one restriction per canton
    seen_lvl: dict[int, Warning] = {}
    kept: list[Warning] = []
    for w in warnings:
        if w.type is WarningType.fire_danger:
            lvl = int(w.params.get("level") or 0)
            if lvl in seen_lvl:
                seen_lvl[lvl].evidence = seen_lvl[lvl].evidence + [
                    e for e in w.evidence if e not in seen_lvl[lvl].evidence
                ]
                continue
            seen_lvl[lvl] = w
        kept.append(w)
    warnings = kept

    # SLF presence
    try:
        lon, lat = (
            prof.lonlat[len(prof.lonlat) // 2] if prof.lonlat else (route.coords[0][0], route.coords[0][1])
        )
        bulletins = SLFAdapter(fetcher).fetch(
            Query(kind="bulletin", bbox=(lon, lat, lon, lat), params={"lang": lang})
        )
        if bulletins:
            b = bulletins[0]
            snap.slf_region = ", ".join(x for x in b.payload.get("regions", []) if x)
            snap.slf_level = b.payload.get("level_max")
            ev = Evidence(
                **{"class": EvidenceClass.A},
                source="ch.slf",
                url=b.url,
                source_ts=b.source_ts,
                retrieved_ts=b.retrieved_ts,
                original_span=b.original_span,
            )
            snap.evidence.append(ev)
            warnings.append(
                _w(
                    WarningType.avalanche_context,
                    Severity.note,
                    [ev],
                    level=snap.slf_level,
                    region=snap.slf_region,
                )
            )
    except SourceUnavailable:
        snap.unavailable.append("ch.slf")
    return snap, warnings


def _weather_warnings(
    snap: ConditionSnapshot, prof: ElevationProfile, exposed: list[Segment], ws: datetime, we: datetime
) -> list[Warning]:
    out: list[Warning] = []
    ev = snap.evidence[:1]
    in_win = [h for h in snap.hours if ws <= h.time <= we]
    if not in_win:
        return out
    gust = max((h.gust_kmh or 0.0) for h in in_win)
    gust_h = max(in_win, key=lambda h: h.gust_kmh or 0.0)
    if exposed and gust >= 50:
        seg = exposed[0]
        out.append(
            _w(
                WarningType.exposed_wind,
                Severity.important if gust >= 60 else Severity.note,
                ev,
                seg=seg,
                gust_kmh=round(gust),
                time=gust_h.time.strftime("%H:%M"),
                from_km=seg.from_km,
                to_km=seg.to_km,
            )
        )
    elif gust >= 70:
        out.append(
            _w(
                WarningType.exposed_wind,
                Severity.important,
                ev,
                gust_kmh=round(gust),
                time=gust_h.time.strftime("%H:%M"),
                from_km=0.0,
                to_km=round(prof.km[-1], 1),
            )
        )
    storm = [h for h in snap.hours if ws <= h.time <= we + timedelta(hours=2) and (h.thunder_prob or 0) >= 50]
    if storm:
        out.append(
            _w(
                WarningType.thunderstorm,
                Severity.important,
                ev,
                probability=100,
                time=storm[0].time.strftime("%H:%M"),
            )
        )
    # precipitation: sum over one sample point (the highest) to avoid triple counting
    highest = max(in_win, key=lambda h: h.elevation_m or 0).km
    precip = sum((h.precip_mm or 0.0) for h in in_win if h.km == highest)
    if precip >= 4:
        out.append(
            _w(
                WarningType.heavy_precipitation,
                Severity.important if precip >= 10 else Severity.note,
                ev,
                mm=round(precip, 1),
                from_time=ws.strftime("%H:%M"),
                to_time=we.strftime("%H:%M"),
            )
        )
    temps = [(h.temp_c, h) for h in in_win if h.temp_c is not None]
    if temps:
        tmax, hmax = max(temps, key=lambda t: t[0])
        tmin, hmin = min(temps, key=lambda t: t[0])
        if tmax is not None and tmax >= 30:
            out.append(
                _w(WarningType.heat, Severity.note, ev, temp_c=round(tmax), time=hmax.time.strftime("%H:%M"))
            )
        if tmin is not None and tmin <= 0:
            out.append(
                _w(WarningType.cold, Severity.note, ev, temp_c=round(tmin), time=hmin.time.strftime("%H:%M"))
            )
    snow = any((h.summary or "").startswith("snow") for h in in_win)
    if snow and prof.max_ele > 0:
        out.append(
            _w(
                WarningType.snow_context,
                Severity.note,
                ev,
                elevation_m=round(prof.min_ele),
                max_elevation_m=round(prof.max_ele),
            )
        )
    return out


def _sample_points(prof: ElevationProfile) -> list[tuple[float, float, float, float]]:
    if not prof.km:
        return []
    kms = sorted({0.0, prof.km_of_max(), prof.km[-1]})
    return [(k, prof.ele_at_km(k), *lonlat_of(prof, k)) for k in kms]


def _point_bbox(prof: ElevationProfile) -> tuple[float, float, float, float]:
    lons = [p[0] for p in prof.lonlat]
    lats = [p[1] for p in prof.lonlat]
    return (min(lons), min(lats), max(lons), max(lats))


def _w(
    t: WarningType, sev: Severity, ev: list[Evidence], seg: Segment | None = None, **params: Any
) -> Warning:
    return Warning(
        type=t, severity=sev, evidence=ev or [_derived(t.value)], affected_segment=seg, params=params
    )


def _derived(what: str) -> Evidence:
    return Evidence(
        **{"class": EvidenceClass.B},
        source="bergbot.core",
        retrieved_ts=datetime.now(tz=UTC),
        translated_summary=f"derived: {what}",
    )


def _local(date: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{date}T{hhmm}:00{ZURICH}")


def _parse_local(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = datetime.fromisoformat(s + ZURICH)
    return dt


def _days_ahead(date: str) -> int:
    d = datetime.fromisoformat(date).date()
    return max(0, (d - datetime.now(tz=UTC).date()).days)
