"""Metric operations. Everything here converts to LV95 (metres), computes, and returns km along the route.
`resample` puts a vertex every 25 m so downstream sampling (weather, slope, exposure) is uniform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from bergbot.core.domain import Segment, SegmentKind
from bergbot.core.geospatial.crs import _to_lv95, _to_wgs


def to_metric(geom: BaseGeometry) -> BaseGeometry:
    return transform(_to_lv95().transform, geom)


def to_wgs(geom: BaseGeometry) -> BaseGeometry:
    return transform(_to_wgs().transform, geom)


@dataclass
class MetricRoute:
    """Route in LV95 with cumulative distance per vertex."""

    line: LineString  # LV95, 2D
    elevations: list[float | None]
    cum_m: list[float]

    @property
    def length_m(self) -> float:
        return float(self.line.length)

    def km_at(self, x: float, y: float) -> float:
        return float(self.line.project(Point(x, y))) / 1000.0

    def point_at_km(self, km: float) -> tuple[float, float]:
        p = self.line.interpolate(min(max(km * 1000.0, 0.0), self.line.length))
        return float(p.x), float(p.y)

    def lonlat_at_km(self, km: float) -> tuple[float, float]:
        x, y = self.point_at_km(km)
        lon, lat = _to_wgs().transform(x, y)
        return float(lon), float(lat)

    def bbox_wgs(self, pad_m: float = 300.0) -> tuple[float, float, float, float]:
        minx, miny, maxx, maxy = self.line.buffer(pad_m).bounds
        lon0, lat0 = _to_wgs().transform(minx, miny)
        lon1, lat1 = _to_wgs().transform(maxx, maxy)
        return (float(lon0), float(lat0), float(lon1), float(lat1))


def metric_route(coords: list[list[float]]) -> MetricRoute:
    xs_ys = [_to_lv95().transform(c[0], c[1]) for c in coords]
    line = LineString(xs_ys)
    cum = [0.0]
    for i in range(1, len(xs_ys)):
        (x0, y0), (x1, y1) = xs_ys[i - 1], xs_ys[i]
        cum.append(cum[-1] + ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
    eles: list[float | None] = [c[2] if len(c) > 2 else None for c in coords]
    return MetricRoute(line=line, elevations=eles, cum_m=cum)


def resample(coords: list[list[float]], step_m: float = 25.0) -> list[list[float]]:
    """Return WGS84 coords with a vertex every `step_m` metres (elevation linearly interpolated when present)."""
    mr = metric_route(coords)
    if mr.length_m <= step_m:
        return [list(c) for c in coords]
    n = int(mr.length_m // step_m)
    has_ele = all(e is not None for e in mr.elevations)
    out: list[list[float]] = []
    j = 0
    for i in range(n + 1):
        d = min(i * step_m, mr.length_m)
        p = mr.line.interpolate(d)
        lon, lat = _to_wgs().transform(p.x, p.y)
        if has_ele:
            while j + 1 < len(mr.cum_m) - 1 and mr.cum_m[j + 1] < d:
                j += 1
            d0, d1 = mr.cum_m[j], mr.cum_m[min(j + 1, len(mr.cum_m) - 1)]
            e0, e1 = mr.elevations[j], mr.elevations[min(j + 1, len(mr.elevations) - 1)]
            t = 0.0 if d1 <= d0 else (d - d0) / (d1 - d0)
            ele = float(e0) + (float(e1) - float(e0)) * t  # type: ignore[arg-type]
            out.append([float(lon), float(lat), round(ele, 1)])
        else:
            out.append([float(lon), float(lat)])
    last = coords[-1]
    if out and (abs(out[-1][0] - last[0]) > 1e-7 or abs(out[-1][1] - last[1]) > 1e-7):
        out.append([float(last[0]), float(last[1])] + ([float(last[2])] if has_ele else []))
    return out


def route_bbox(coords: list[list[float]], pad_m: float = 300.0) -> tuple[float, float, float, float]:
    return metric_route(coords).bbox_wgs(pad_m)


def is_loop(coords: list[list[float]], tol_m: float = 250.0) -> bool:
    mr = metric_route(coords)
    a, b = mr.line.coords[0], mr.line.coords[-1]
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 <= tol_m and mr.length_m > 3 * tol_m


def intersect_segments(
    coords: list[list[float]],
    geometry: dict[str, Any],
    buffer_m: float = 0.0,
    kind: SegmentKind = SegmentKind.hazard,
    label: str | None = None,
    min_len_m: float = 5.0,
) -> list[Segment]:
    """Return the km ranges of the route that lie inside `geometry` (WGS84 GeoJSON polygon / line buffered).
    Lines (closures) are buffered by `buffer_m` (default 15 m if 0) so an overlapping trail registers."""
    mr = metric_route(coords)
    g = to_metric(shape(geometry))
    if isinstance(g, LineString | MultiLineString) and buffer_m <= 0:
        buffer_m = 15.0
    if buffer_m > 0:
        g = g.buffer(buffer_m)
    if not isinstance(g, Polygon | MultiPolygon):
        return []
    inter = mr.line.intersection(g)
    if inter.is_empty:
        return []
    parts: list[LineString] = []
    if isinstance(inter, LineString):
        parts = [inter]
    elif isinstance(inter, MultiLineString):
        parts = list(inter.geoms)
    else:
        parts = [p for p in getattr(inter, "geoms", []) if isinstance(p, LineString)]
    segs: list[Segment] = []
    for part in parts:
        if part.length < min_len_m:
            continue
        a = mr.line.project(Point(part.coords[0])) / 1000.0
        b = mr.line.project(Point(part.coords[-1])) / 1000.0
        lo, hi = sorted((a, b))
        segs.append(Segment(from_km=round(lo, 2), to_km=round(hi, 2), kind=kind, label=label))
    return merge_segments(segs)


def merge_segments(segs: list[Segment], gap_km: float = 0.05) -> list[Segment]:
    if not segs:
        return []
    segs = sorted(segs, key=lambda s: s.from_km)
    out = [segs[0]]
    for s in segs[1:]:
        last = out[-1]
        if s.from_km <= last.to_km + gap_km and s.kind == last.kind and s.label == last.label:
            out[-1] = last.model_copy(update={"to_km": max(last.to_km, s.to_km)})
        else:
            out.append(s)
    return out


def distance_to_route_m(coords: list[list[float]], lon: float, lat: float) -> tuple[float, float]:
    """(distance in metres from the point to the route, km along route of the nearest point)."""
    mr = metric_route(coords)
    x, y = _to_lv95().transform(lon, lat)
    p = Point(x, y)
    return float(mr.line.distance(p)), float(mr.line.project(p)) / 1000.0


def within_bbox(bbox: tuple[float, float, float, float], lon: float, lat: float) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def overlap_fraction(coords: list[list[float]], other: dict[str, Any], buffer_m: float = 30.0) -> float:
    """Fraction of the route length lying within `buffer_m` of the other geometry (identity matching)."""
    mr = metric_route(coords)
    g = to_metric(shape(other)).buffer(buffer_m)
    inter = mr.line.intersection(g)
    return float(inter.length / mr.line.length) if mr.line.length else 0.0
