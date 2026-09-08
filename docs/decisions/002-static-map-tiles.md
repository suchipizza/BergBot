# 002 — Static map tiles for the report

**Decision:** use swisstopo WMTS `ch.swisstopo.pixelkarte-farbe` (Web Mercator, EPSG:3857) tiles, stitched
server-side into one JPEG ≤ 400 KB and embedded as a data URI in the report. Attribution "© swisstopo"
is printed under the map.

**Why:** swisstopo made its map data OGD on 1 March 2021; free use including commercial with attribution.
It is the map Swiss hikers already know (same as the swisstopo app), so the report map matches what they will
navigate with. OSM raster is the fallback (`--no-map` or on fetch failure the route is drawn on a blank grid
with a "map unavailable" line) — the report must never fail because of a tile.

**Constraints:** the report's tile image is only ever embedded in that report file; tiles are not bundled in the
repo or cached beyond the per-user cache TTL.
