"""Candidate routes for `find` / `around` — always subsets of the official network (SR-5).

Two generators, both deterministic:
1. Named SwitzerlandMobility stages (`ch.astra.wanderland`) intersecting the search area.
2. Graph walks on swissTLM3D trail segments: from the start node (nearest network node to the place or its
   nearest stop) shortest paths to destination nodes (huts, viewpoints, lift stations, summits from OSM/GeoAdmin)
   within the distance budget → out-and-back routes, plus A→B to another stop when one lies near the destination.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, MultiLineString, shape

from bergbot.core.domain import Activity, Constraint, Place, PlaceKind, Route, RouteIdentity
from bergbot.core.geospatial.crs import to_lv95, to_wgs84
from bergbot.core.geospatial.ops import to_metric
from bergbot.sources.base import Query, SourceUnavailable
from bergbot.sources.ch.hiking_network import HikingNetworkAdapter, WanderlandRoutesAdapter
from bergbot.sources.http import Fetcher
from bergbot.sources.shared.osm import OSMAdapter

SNAP_M = 8.0


def search_bbox(place: Place, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(place.lat)))
    return (place.lon - dlon, place.lat - dlat, place.lon + dlon, place.lat + dlat)


def radius_for(constraints: Constraint, place: Place | None = None) -> float:
    if place is not None and place.source == "data/cantons.json" and not constraints.place:
        return 12.0
    if constraints.max_distance_km:
        return max(3.0, min(constraints.max_distance_km * 0.6, 12.0))
    return 6.0


@dataclass
class Node:
    x: float
    y: float
    id: int


class TrailGraph:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.adj: dict[int, list[tuple[int, float, int]]] = defaultdict(
            list
        )  # node -> [(other, length_m, edge_id)]
        self.edges: list[LineString] = []
        self._grid: dict[tuple[int, int], list[int]] = defaultdict(list)

    def _node(self, x: float, y: float) -> int:
        cell = (int(x // SNAP_M), int(y // SNAP_M))
        for cx in (cell[0] - 1, cell[0], cell[0] + 1):
            for cy in (cell[1] - 1, cell[1], cell[1] + 1):
                for nid in self._grid[(cx, cy)]:
                    n = self.nodes[nid]
                    if (n.x - x) ** 2 + (n.y - y) ** 2 <= SNAP_M**2:
                        return nid
        nid = len(self.nodes)
        self.nodes.append(Node(x, y, nid))
        self._grid[cell].append(nid)
        return nid

    def add_line(self, line: LineString) -> None:
        if line.length < 1.0:
            return
        a = self._node(*line.coords[0])
        b = self._node(*line.coords[-1])
        eid = len(self.edges)
        self.edges.append(line)
        self.adj[a].append((b, float(line.length), eid))
        self.adj[b].append((a, float(line.length), eid))

    def nearest(self, x: float, y: float, max_m: float = 400.0) -> int | None:
        best, best_d = None, max_m
        for n in self.nodes:
            d = math.hypot(n.x - x, n.y - y)
            if d < best_d:
                best, best_d = n.id, d
        return best

    def dijkstra(self, src: int, limit_m: float) -> tuple[dict[int, float], dict[int, tuple[int, int]]]:
        dist = {src: 0.0}
        prev: dict[int, tuple[int, int]] = {}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, float("inf")) or d > limit_m:
                continue
            for v, w, eid in self.adj[u]:
                nd = d + w
                if nd < dist.get(v, float("inf")) and nd <= limit_m:
                    dist[v] = nd
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    def path_coords(self, prev: dict[int, tuple[int, int]], src: int, dst: int) -> list[tuple[float, float]]:
        coords: list[tuple[float, float]] = []
        cur = dst
        while cur != src:
            u, eid = prev[cur]
            line = self.edges[eid]
            pts = list(line.coords)
            # orient from u to cur
            if math.hypot(pts[0][0] - self.nodes[cur].x, pts[0][1] - self.nodes[cur].y) < SNAP_M:
                pts = pts[::-1]
            coords = pts[:-1] + coords if coords else pts
            cur = u
        return coords


def tiles(
    bbox: tuple[float, float, float, float], cell_km: float = 2.5
) -> list[tuple[float, float, float, float]]:
    """Split a bbox into cells so each GeoAdmin identify call stays under its 200-feature cap."""
    lat_mid = (bbox[1] + bbox[3]) / 2
    dlat = cell_km / 111.0
    dlon = cell_km / (111.0 * math.cos(math.radians(lat_mid)))
    out = []
    lat = bbox[1]
    while lat < bbox[3]:
        lon = bbox[0]
        while lon < bbox[2]:
            out.append((lon, lat, min(lon + dlon, bbox[2]), min(lat + dlat, bbox[3])))
            lon += dlon
        lat += dlat
    return out


def build_graph(bbox: tuple[float, float, float, float], fetcher: Fetcher | None) -> TrailGraph:
    g = TrailGraph()
    adapter = HikingNetworkAdapter(fetcher)
    seen: set[str] = set()
    for cell in tiles(bbox):
        for r in adapter.fetch(Query(kind="trails", bbox=cell)):
            fid = str(r.payload.get("feature_id"))
            geom = r.payload.get("geometry")
            if not geom or fid in seen:
                continue
            seen.add(fid)
            m = to_metric(shape(geom))
            lines = (
                list(m.geoms) if isinstance(m, MultiLineString) else [m] if isinstance(m, LineString) else []
            )
            for line in lines:
                g.add_line(line)
    return g


def named_stage_candidates(
    bbox: tuple[float, float, float, float], fetcher: Fetcher | None, activity: Activity
) -> list[Route]:
    out: list[Route] = []
    try:
        recs = WanderlandRoutesAdapter(fetcher).fetch(Query(kind="routes", bbox=bbox))
    except SourceUnavailable:
        return out
    seen: set[str] = set()
    for r in recs:
        geom = r.payload.get("geometry")
        name = r.payload.get("name")
        if not geom or not name or name in seen:
            continue
        seen.add(name)
        coords = _longest_line(geom)
        if len(coords) < 2:
            continue
        out.append(
            Route(
                geometry={"type": "LineString", "coordinates": coords},
                identity=RouteIdentity(
                    name=name,
                    official_id=str(r.payload.get("feature_id")),
                    network="ch.astra.wanderland",
                    overlap_pct=100.0,
                    famous=r.payload.get("prominence") in ("national", "regional"),
                    famous_reason=f"SwitzerlandMobility {r.payload.get('prominence')} route {r.payload.get('route_number')}"
                    if r.payload.get("prominence") in ("national", "regional")
                    else None,
                ),
                activity=activity,
                network_member=True,
            )
        )
    return out


def graph_candidates(
    place: Place,
    bbox: tuple[float, float, float, float],
    constraints: Constraint,
    fetcher: Fetcher | None,
    activity: Activity,
    max_routes: int = 6,
) -> list[Route]:
    graph_bbox = search_bbox(place, min(3.5, radius_for(constraints)))
    try:
        g = build_graph(graph_bbox, fetcher)
    except SourceUnavailable:
        return []
    if not g.nodes:
        return []
    sx, sy = to_lv95(place.lon, place.lat)
    src = g.nearest(sx, sy, max_m=1000.0)
    if src is None:
        return []
    budget_m = (constraints.max_distance_km or 12.0) * 1000.0 / 2.0
    dist, prev = g.dijkstra(src, budget_m)
    # destinations: OSM POIs and network nodes far from start (hut, viewpoint, lift, summit)
    targets: list[tuple[str, float, float, str]] = []
    try:
        for a in OSMAdapter(fetcher).fetch(Query(kind="amenities", bbox=bbox)):
            if a.kind in ("hut", "restaurant", "lift", "poi", "shelter") and a.payload.get("name"):
                x, y = to_lv95(a.payload["lon"], a.payload["lat"])
                targets.append((a.payload["name"], x, y, a.kind))
    except SourceUnavailable:
        pass
    routes: list[Route] = []
    used: set[int] = set()
    scored: list[tuple[float, str, int, str]] = []
    for name, x, y, kind in targets:
        nid = g.nearest(x, y, max_m=150.0)
        if nid is None or nid == src or nid not in dist or nid in used:
            continue
        if name.strip().lower() == place.name.strip().lower():
            continue
        d = dist[nid]
        if d < 1200.0:
            continue
        used.add(nid)
        pref = {"hut": 0, "poi": 1, "lift": 2, "restaurant": 3, "shelter": 4}[kind]
        scored.append((pref + d / 1e6, name, nid, kind))
    scored.sort()
    for _, name, nid, _kind in scored[:max_routes]:
        path = g.path_coords(prev, src, nid)
        if len(path) < 2:
            continue
        loop = path + path[-2::-1]
        coords = [[*to_wgs84(x, y)] for x, y in loop]
        start_name = place.name
        routes.append(
            Route(
                geometry={"type": "LineString", "coordinates": coords},
                identity=RouteIdentity(
                    name=f"{start_name} – {name} – {start_name}",
                    network="ch.swisstopo.swisstlm3d-wanderwege",
                    overlap_pct=100.0,
                ),
                activity=activity,
                network_member=True,
                is_loop=True,
                start=Place(name=start_name, kind=PlaceKind.route_point, lon=place.lon, lat=place.lat),
                end=Place(name=start_name, kind=PlaceKind.route_point, lon=place.lon, lat=place.lat),
            )
        )
    return routes


def _longest_line(geom: dict[str, Any]) -> list[list[float]]:
    if geom.get("type") == "LineString":
        return [list(c[:2]) for c in geom["coordinates"]]
    if geom.get("type") == "MultiLineString":
        lines = sorted(geom["coordinates"], key=len, reverse=True)
        return [list(c[:2]) for c in lines[0]] if lines else []
    return []
