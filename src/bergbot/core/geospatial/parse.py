"""Parse GPX / KML / GeoJSON into a `Route` (GeoJSON LineString, WGS84, optional elevation).
Multi-segment tracks are concatenated in order; routes (`<rte>`) are used when no track exists."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import gpxpy

from bergbot.core.domain import Route, RouteIdentity


class RouteParseError(ValueError):
    pass


def parse_route_file(path: Path, name: str | None = None) -> Route:
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".gpx" or "<gpx" in text[:2000]:
        coords, found_name = _parse_gpx(text)
    elif suffix == ".kml" or "<kml" in text[:2000]:
        coords, found_name = _parse_kml(text)
    elif suffix in (".geojson", ".json") or text.lstrip().startswith("{"):
        coords, found_name = _parse_geojson(text)
    else:
        raise RouteParseError(f"unsupported route file: {path.name}")
    if len(coords) < 2:
        raise RouteParseError(f"no track with ≥ 2 points in {path.name}")
    coords = _dedupe(coords)
    return Route(
        geometry={"type": "LineString", "coordinates": coords},
        identity=RouteIdentity(name=name or found_name or path.stem),
        source_file=path.name,
    )


def _parse_gpx(text: str) -> tuple[list[list[float]], str | None]:
    gpx = gpxpy.parse(text)
    coords: list[list[float]] = []
    name: str | None = gpx.name
    for trk in gpx.tracks:
        name = name or trk.name
        for seg in trk.segments:
            for p in seg.points:
                coords.append(_pt(p.longitude, p.latitude, p.elevation))
    if not coords:
        for rte in gpx.routes:
            name = name or rte.name
            for rp in rte.points:
                coords.append(_pt(rp.longitude, rp.latitude, rp.elevation))
    return coords, name


def _parse_kml(text: str) -> tuple[list[list[float]], str | None]:
    root = ET.fromstring(text)
    ns = {"k": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    prefix = "k:" if ns else ""
    coords: list[list[float]] = []
    name = None
    for pm in root.iter(f"{{{ns['k']}}}Placemark" if ns else "Placemark"):
        nm = pm.find(f"{prefix}name", ns)
        for ls in pm.iter(f"{{{ns['k']}}}LineString" if ns else "LineString"):
            c = ls.find(f"{prefix}coordinates", ns)
            if c is None or not c.text:
                continue
            name = name or (nm.text if nm is not None else None)
            for tok in re.split(r"\s+", c.text.strip()):
                parts = tok.split(",")
                if len(parts) >= 2:
                    coords.append(
                        _pt(float(parts[0]), float(parts[1]), float(parts[2]) if len(parts) > 2 else None)
                    )
    if not coords:
        # gx:Track
        for when_coord in root.iter("{http://www.google.com/kml/ext/2.2}coord"):
            parts = (when_coord.text or "").split()
            if len(parts) >= 2:
                coords.append(
                    _pt(float(parts[0]), float(parts[1]), float(parts[2]) if len(parts) > 2 else None)
                )
    return coords, name


def _parse_geojson(text: str) -> tuple[list[list[float]], str | None]:
    doc = json.loads(text)
    name = None
    geoms: list[dict[str, Any]] = []
    if doc.get("type") == "FeatureCollection":
        for f in doc.get("features", []):
            name = name or (f.get("properties") or {}).get("name")
            if f.get("geometry"):
                geoms.append(f["geometry"])
    elif doc.get("type") == "Feature":
        name = (doc.get("properties") or {}).get("name")
        geoms.append(doc["geometry"])
    else:
        geoms.append(doc)
    coords: list[list[float]] = []
    for g in geoms:
        if g.get("type") == "LineString":
            coords.extend(_pt(*c[:3]) for c in g["coordinates"])
        elif g.get("type") == "MultiLineString":
            for line in g["coordinates"]:
                coords.extend(_pt(*c[:3]) for c in line)
    return coords, name


def _pt(lon: float, lat: float, ele: float | None = None) -> list[float]:
    return [float(lon), float(lat), float(ele)] if ele is not None else [float(lon), float(lat)]


def _dedupe(coords: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for c in coords:
        if out and abs(out[-1][0] - c[0]) < 1e-7 and abs(out[-1][1] - c[1]) < 1e-7:
            continue
        out.append(c)
    return out
