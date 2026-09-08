"""Export a Route as GPX (default), KML or GeoJSON. Files are what the user imports into swisstopo."""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

import gpxpy.gpx

from bergbot.core.domain import Route


def export_route(route: Route, fmt: str, target: Path) -> Path:
    fmt = fmt.lower()
    if fmt == "gpx":
        target.write_text(to_gpx(route), encoding="utf-8")
    elif fmt == "kml":
        target.write_text(to_kml(route), encoding="utf-8")
    elif fmt == "geojson":
        target.write_text(to_geojson(route), encoding="utf-8")
    else:
        raise ValueError(f"unknown format {fmt}")
    return target


def to_gpx(route: Route) -> str:
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "Bergbot — https://github.com/suchipizza/BergBot"
    gpx.name = route.name
    trk = gpxpy.gpx.GPXTrack(name=route.name)
    seg = gpxpy.gpx.GPXTrackSegment()
    for c in route.coords:
        seg.points.append(
            gpxpy.gpx.GPXTrackPoint(latitude=c[1], longitude=c[0], elevation=c[2] if len(c) > 2 else None)
        )
    trk.segments.append(seg)
    gpx.tracks.append(trk)
    if route.start:
        gpx.waypoints.append(
            gpxpy.gpx.GPXWaypoint(latitude=route.start.lat, longitude=route.start.lon, name=route.start.name)
        )
    if route.end:
        gpx.waypoints.append(
            gpxpy.gpx.GPXWaypoint(latitude=route.end.lat, longitude=route.end.lon, name=route.end.name)
        )
    return gpx.to_xml()


def to_kml(route: Route) -> str:
    coords = " ".join(",".join(str(v) for v in c) for c in route.coords)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"<name>{escape(route.name)}</name><Placemark><name>{escape(route.name)}</name>"
        f"<LineString><tessellate>1</tessellate><coordinates>{coords}</coordinates></LineString></Placemark></Document></kml>\n"
    )


def to_geojson(route: Route) -> str:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": route.name, "activity": route.activity.value},
                    "geometry": route.geometry,
                }
            ],
        },
        ensure_ascii=False,
    )
