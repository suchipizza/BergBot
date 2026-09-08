"""Inline SVG map: route over an embedded swisstopo raster (data URI) or a blank grid, severity-coloured hazard
segments, markers for start/end/escape points/huts/stops/webcams, scale bar, legend hooks."""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from bergbot.core.domain import Audit, SegmentKind
from bergbot.core.geospatial.ops import metric_route
from bergbot.i18n import Locale

SEG_COLOUR = {
    SegmentKind.closure: "#c8102e",
    SegmentKind.hazard: "#e07b00",
    SegmentKind.zone: "#e07b00",
    SegmentKind.exposed: "#7a3db8",
    SegmentKind.steep: "#7a3db8",
    SegmentKind.flat: "#1f6feb",
}


def _merc_y(lat: float) -> float:
    lat = max(-85.0, min(85.0, lat))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


@dataclass
class Projection:
    bbox: tuple[float, float, float, float]
    width: int
    height: int

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        x = (lon - self.bbox[0]) / (self.bbox[2] - self.bbox[0]) * self.width
        y0, y1 = _merc_y(self.bbox[3]), _merc_y(self.bbox[1])
        y = (_merc_y(lat) - y0) / (y1 - y0) * self.height
        return x, y


def padded_bbox(audit: Audit) -> tuple[float, float, float, float]:
    lons = [c[0] for c in audit.route.coords]
    lats = [c[1] for c in audit.route.coords]
    for p in audit.escape_points:
        lons.append(p.lon)
        lats.append(p.lat)
    minlon, maxlon, minlat, maxlat = min(lons), max(lons), min(lats), max(lats)
    dlon = max(maxlon - minlon, 0.01)
    dlat = max(maxlat - minlat, 0.006)
    pad_lon, pad_lat = dlon * 0.2, dlat * 0.25
    return (minlon - pad_lon, minlat - pad_lat, maxlon + pad_lon, maxlat + pad_lat)


def render_map_svg(audit: Audit, L: Locale, tiles: dict[str, Any] | None, width: int = 720) -> str:
    bbox = tiles["bbox"] if tiles else padded_bbox(audit)
    if tiles:
        height = int(width * tiles["height"] / tiles["width"])
    else:
        # keep aspect from mercator extents
        span_x = bbox[2] - bbox[0]
        span_y = (_merc_y(bbox[3]) - _merc_y(bbox[1])) * 180 / math.pi
        height = int(width * span_y / span_x) if span_x else width
        height = max(240, min(height, 900))
    proj = Projection(bbox=bbox, width=width, height=height)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(L.t("report.sections.route"))}" class="map">'
    ]
    if tiles:
        uri = "data:image/jpeg;base64," + base64.b64encode(tiles["jpeg"]).decode("ascii")
        parts.append(
            f'<image href="{uri}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none"/>'
        )
    else:
        parts.append(f'<rect width="{width}" height="{height}" fill="#eef2f5"/>')
        for i in range(1, 8):
            x = width * i / 8
            y = height * i / 8
            parts.append(
                f'<line x1="{x:.0f}" y1="0" x2="{x:.0f}" y2="{height}" stroke="#d9e0e6" stroke-width="1"/>'
            )
            parts.append(
                f'<line x1="0" y1="{y:.0f}" x2="{width}" y2="{y:.0f}" stroke="#d9e0e6" stroke-width="1"/>'
            )
    # route
    pts = [proj.xy(c[0], c[1]) for c in audit.route.coords]
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    parts.append(
        f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>'
    )
    parts.append(
        f'<path d="{d}" fill="none" stroke="#1f6feb" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    # hazard segments
    mr = metric_route(audit.route.coords)
    for seg in audit.route.segments:
        colour = SEG_COLOUR.get(seg.kind, "#e07b00")
        n = max(2, int((seg.to_km - seg.from_km) * 1000 / 25) + 1)
        seg_pts = []
        for i in range(n):
            km = seg.from_km + (seg.to_km - seg.from_km) * i / (n - 1)
            lon, lat = mr.lonlat_at_km(km)
            seg_pts.append(proj.xy(lon, lat))
        sd = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in seg_pts)
        parts.append(
            f'<path d="{sd}" fill="none" stroke="{colour}" stroke-width="6" stroke-linecap="round"><title>{escape(seg.label or seg.kind.value)} km {seg.from_km}–{seg.to_km}</title></path>'
        )
    # markers: huts, stops, webcams, escape points
    for a in audit.amenities:
        if a.kind.value in ("hut", "restaurant"):
            x, y = proj.xy(a.lon, a.lat)
            parts.append(
                f'<g><title>{escape(a.name)}</title><path d="M {x:.1f} {y - 7:.1f} l 7 7 h -14 z" fill="#8a5a1a" stroke="#fff" stroke-width="1.2"/></g>'
            )
        elif a.kind.value == "lift":
            x, y = proj.xy(a.lon, a.lat)
            parts.append(
                f'<g><title>{escape(a.name)}</title><rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="#444" stroke="#fff" stroke-width="1.2" transform="rotate(45 {x:.1f} {y:.1f})"/></g>'
            )
    for p in audit.escape_points:
        x, y = proj.xy(p.lon, p.lat)
        parts.append(
            f'<g><title>{escape(p.name)}</title><rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="#2b8a3e" stroke="#fff" stroke-width="1.2"/></g>'
        )
    for w in audit.webcams:
        x, y = proj.xy(w.lon, w.lat)
        parts.append(
            f'<g><title>{escape(w.name)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#0b7285" stroke="#fff" stroke-width="1.2"/></g>'
        )
    # start / end
    sx, sy = pts[0]
    ex, ey = pts[-1]
    parts.append(
        f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="8" fill="#2b8a3e" stroke="#fff" stroke-width="2"/><text x="{sx:.1f}" y="{sy + 4:.1f}" font-size="10" font-weight="700" fill="#fff" text-anchor="middle" font-family="system-ui,sans-serif">S</text>'
    )
    parts.append(
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="8" fill="#c8102e" stroke="#fff" stroke-width="2"/><text x="{ex:.1f}" y="{ey + 4:.1f}" font-size="10" font-weight="700" fill="#fff" text-anchor="middle" font-family="system-ui,sans-serif">E</text>'
    )
    # scale bar (1 km or 500 m)
    mid_lat = (bbox[1] + bbox[3]) / 2
    m_per_px = (bbox[2] - bbox[0]) * 111_320 * math.cos(math.radians(mid_lat)) / width
    bar_m = 1000 if 1000 / m_per_px < width / 3 else 500
    bar_px = bar_m / m_per_px
    parts.append(
        f'<rect x="12" y="{height - 26}" width="{bar_px + 8:.0f}" height="18" fill="#fff" opacity="0.8" rx="3"/>'
    )
    parts.append(
        f'<line x1="16" y1="{height - 14}" x2="{16 + bar_px:.0f}" y2="{height - 14}" stroke="#222" stroke-width="3"/>'
    )
    parts.append(
        f'<text x="{16 + bar_px / 2:.0f}" y="{height - 17}" font-size="10" text-anchor="middle" fill="#222" font-family="system-ui,sans-serif">{bar_m if bar_m < 1000 else 1} {"m" if bar_m < 1000 else "km"}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)
