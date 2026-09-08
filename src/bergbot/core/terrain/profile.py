"""Elevation profile and derived terrain facts.

Sources, in order: GeoAdmin `profile.json` (swissALTI3D, evidence A→B) — fallback: elevations embedded in the
route file (evidence B, lower confidence). Ascent/descent use a 125 m moving average and 5 m hysteresis so GPS
noise does not inflate totals. Exposure is a heuristic (class D): sustained steep slope at altitude, or sharp
bearing changes on steep ground (ridge/switchback signature)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

from shapely.geometry import LineString

from bergbot.core.domain import Evidence, EvidenceClass, Route, RouteStats, Segment, SegmentKind
from bergbot.core.geospatial.crs import _to_wgs
from bergbot.core.geospatial.ops import metric_route, resample
from bergbot.sources.base import SourceUnavailable
from bergbot.sources.ch.geoadmin import GeoAdminAdapter
from bergbot.sources.http import Fetcher

STEP_M = 25.0


@dataclass
class ElevationProfile:
    km: list[float]
    ele: list[float]
    lonlat: list[tuple[float, float]]
    source: str
    evidence: Evidence | None = None
    slope_pct: list[float] = field(default_factory=list)  # per step (len == len(km))
    bearing_deg: list[float] = field(default_factory=list)

    @property
    def max_ele(self) -> float:
        return max(self.ele) if self.ele else 0.0

    @property
    def min_ele(self) -> float:
        return min(self.ele) if self.ele else 0.0

    def km_of_max(self) -> float:
        return self.km[self.ele.index(self.max_ele)] if self.ele else 0.0

    def ele_at_km(self, km: float) -> float:
        if not self.km:
            return 0.0
        for i, k in enumerate(self.km):
            if k >= km:
                return self.ele[i]
        return self.ele[-1]


def build_profile(route: Route, fetcher: Fetcher | None = None, offline: bool = False) -> ElevationProfile:
    coords = resample(route.coords, STEP_M)
    mr = metric_route(coords)
    km = [c / 1000.0 for c in mr.cum_m]
    lonlat = [(c[0], c[1]) for c in coords]
    prof: ElevationProfile | None = None
    if not offline:
        try:
            prof = _geoadmin_profile(route, km, lonlat, fetcher)
        except SourceUnavailable:
            prof = None
    if prof is None:
        if all(len(c) > 2 for c in coords):
            prof = ElevationProfile(
                km=km,
                ele=[float(c[2]) for c in coords],
                lonlat=lonlat,
                source="route_file",
                evidence=Evidence(
                    **{"class": EvidenceClass.B},
                    source="route_file",
                    retrieved_ts=_now(),
                    confidence=0.6,
                    translated_summary="elevations from the route file",
                ),
            )
        else:
            prof = ElevationProfile(km=km, ele=[0.0] * len(km), lonlat=lonlat, source="none")
    prof.ele = _smooth(prof.ele, window=5)
    prof.slope_pct = _slopes(prof.km, prof.ele)
    prof.bearing_deg = _bearings(mr.line)
    return prof


def _geoadmin_profile(
    route: Route, km: list[float], lonlat: list[tuple[float, float]], fetcher: Fetcher | None
) -> ElevationProfile:
    # simplify to keep the GET URL short; the service resamples anyway
    line = LineString([(c[0], c[1]) for c in route.coords])
    simple = line.simplify(0.00005, preserve_topology=False)  # ≈ 4–5 m
    if len(simple.coords) > 600:
        simple = line.simplify(0.0002, preserve_topology=False)
    if len(simple.coords) > 600:
        simple = LineString(list(simple.coords)[:: max(1, len(simple.coords) // 600)] + [simple.coords[-1]])
    nb = max(20, min(int(km[-1] * 1000 / STEP_M) + 1, 3000))
    rec = GeoAdminAdapter(fetcher).profile(
        {"type": "LineString", "coordinates": [list(c) for c in simple.coords]}, nb_points=nb
    )
    samples = [s for s in rec.payload["samples"] if s.get("alt_m") is not None]
    if len(samples) < 2:
        raise SourceUnavailable("ch.geoadmin", "profile (empty)")
    # map service samples (dist along simplified line) onto our km grid by proportional distance
    total_s = samples[-1]["dist_m"] or 1.0
    total_r = km[-1] * 1000.0 or 1.0
    eles: list[float] = []
    j = 0
    for k in km:
        d = k * 1000.0 / total_r * total_s
        while j + 1 < len(samples) and samples[j + 1]["dist_m"] < d:
            j += 1
        s0, s1 = samples[j], samples[min(j + 1, len(samples) - 1)]
        span = (s1["dist_m"] - s0["dist_m"]) or 1.0
        t = min(max((d - s0["dist_m"]) / span, 0.0), 1.0)
        eles.append(float(s0["alt_m"]) + (float(s1["alt_m"]) - float(s0["alt_m"])) * t)
    ev = Evidence(
        **{"class": EvidenceClass.A},
        source="ch.geoadmin",
        url=rec.url,
        retrieved_ts=rec.retrieved_ts,
        confidence=0.95,
        translated_summary=f"elevation profile from swissALTI3D ({rec.payload.get('model')})",
    )
    return ElevationProfile(km=km, ele=eles, lonlat=lonlat, source="ch.geoadmin", evidence=ev)


def _smooth(vals: list[float], window: int = 5) -> list[float]:
    if len(vals) < window:
        return vals
    half = window // 2
    out = []
    for i in range(len(vals)):
        lo, hi = max(0, i - half), min(len(vals), i + half + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def _slopes(km: list[float], ele: list[float]) -> list[float]:
    out = [0.0]
    for i in range(1, len(km)):
        run = (km[i] - km[i - 1]) * 1000.0
        out.append(((ele[i] - ele[i - 1]) / run * 100.0) if run > 0 else 0.0)
    return out


def _bearings(line: LineString) -> list[float]:
    cs = list(line.coords)
    out = [0.0]
    for i in range(1, len(cs)):
        dx, dy = cs[i][0] - cs[i - 1][0], cs[i][1] - cs[i - 1][1]
        out.append((math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0)
    return out


def ascent_descent(ele: list[float], hysteresis_m: float = 5.0) -> tuple[float, float]:
    if len(ele) < 2:
        return 0.0, 0.0
    up = down = 0.0
    ref = ele[0]
    direction = 0  # +1 climbing, -1 descending
    for e in ele[1:]:
        delta = e - ref
        if direction >= 0 and delta >= hysteresis_m:
            up += delta
            ref = e
            direction = 1
        elif direction <= 0 and delta <= -hysteresis_m:
            down += -delta
            ref = e
            direction = -1
        elif direction == 1 and e > ref:
            up += e - ref
            ref = e
        elif direction == -1 and e < ref:
            down += ref - e
            ref = e
        elif direction == 1 and delta <= -hysteresis_m:
            down += -delta
            ref = e
            direction = -1
        elif direction == -1 and delta >= hysteresis_m:
            up += delta
            ref = e
            direction = 1
    return round(up), round(down)


def sac_duration_min(distance_km: float, ascent_m: float, descent_m: float) -> int:
    """SAC hiking time: horizontal 4 km/h, ascent 400 m/h, descent 800 m/h; total = larger + half the smaller."""
    horiz = distance_km / 4.0
    vert = ascent_m / 400.0 + descent_m / 800.0
    hours = max(horiz, vert) + 0.5 * min(horiz, vert)
    return int(round(hours * 60))


def compute_stats(route: Route, prof: ElevationProfile) -> RouteStats:
    dist_km = prof.km[-1] if prof.km else 0.0
    up, down = ascent_descent(prof.ele) if prof.source != "none" else (0.0, 0.0)
    return RouteStats(
        distance_km=round(dist_km, 2),
        ascent_m=up,
        descent_m=down,
        duration_min=sac_duration_min(dist_km, up, down),
        duration_method="sac",
        min_elevation_m=round(prof.min_ele) if prof.source != "none" else None,
        max_elevation_m=round(prof.max_ele) if prof.source != "none" else None,
        n_points=len(route.coords),
    )


def exposed_segments(
    prof: ElevationProfile, steep_pct: float = 25.0, min_len_m: float = 100.0, min_ele_m: float = 1600.0
) -> list[Segment]:
    """Heuristic (class D): ≥ `min_len_m` of |slope| ≥ `steep_pct` above `min_ele_m`, or steep ground with sharp
    bearing changes (ridge / switchback signature) above `min_ele_m` - 200."""
    if prof.source == "none" or len(prof.km) < 3:
        return []
    segs: list[Segment] = []
    start: int | None = None
    for i in range(1, len(prof.km)):
        steep = abs(prof.slope_pct[i]) >= steep_pct
        high = prof.ele[i] >= min_ele_m
        turn = (
            i > 1
            and _angle_diff(prof.bearing_deg[i], prof.bearing_deg[i - 1]) >= 60
            and abs(prof.slope_pct[i]) >= steep_pct * 0.7
            and prof.ele[i] >= min_ele_m - 200
        )
        hit = (steep and high) or turn
        if hit and start is None:
            start = i - 1
        elif not hit and start is not None:
            _close(segs, prof, start, i - 1, min_len_m)
            start = None
    if start is not None:
        _close(segs, prof, start, len(prof.km) - 1, min_len_m)
    return segs


def _close(segs: list[Segment], prof: ElevationProfile, a: int, b: int, min_len_m: float) -> None:
    if (prof.km[b] - prof.km[a]) * 1000.0 >= min_len_m:
        slope = max(abs(s) for s in prof.slope_pct[a : b + 1]) if b > a else 0.0
        segs.append(
            Segment(
                from_km=round(prof.km[a], 2),
                to_km=round(prof.km[b], 2),
                kind=SegmentKind.exposed,
                slope_pct=round(slope, 1),
                aspect_deg=round(prof.bearing_deg[b], 0),
            )
        )


def _angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def lonlat_of(prof: ElevationProfile, km: float) -> tuple[float, float]:
    for i, k in enumerate(prof.km):
        if k >= km:
            return prof.lonlat[i]
    return prof.lonlat[-1]


def _now() -> datetime:
    return datetime.now(tz=UTC)


__all__ = [
    "ElevationProfile",
    "build_profile",
    "compute_stats",
    "exposed_segments",
    "ascent_descent",
    "sac_duration_min",
    "lonlat_of",
    "_to_wgs",
]
