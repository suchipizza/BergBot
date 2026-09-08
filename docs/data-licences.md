# Data licences and redistribution matrix

Rule (CLAUDE.md #7): before bundling any dataset, record it here. If redistribution is not clearly allowed,
Bergbot fetches at runtime and never bundles. "Bundled" means shipped in the repo or wheel; "cached" means
written to the user's `~/.bergbot/cache` at runtime with a TTL.

| Adapter id | Source | Licence | Redistribution | Bundled? | Attribution string | Update frequency / TTL |
|---|---|---|---|---|---|---|
| ch.geoadmin | api3.geo.admin.ch (search, profile, identify) | OGD (opendata.swiss "Open use. Must provide the source.") | yes, with attribution | no — runtime, cached 7 d for static layers | © swisstopo | live |
| ch.swisstopo_tiles | wmts.geo.admin.ch (ch.swisstopo.pixelkarte-farbe) | OGD, free use with attribution (since 1 Mar 2021) | yes, with attribution | no — tiles fetched per report and embedded in that report only | © swisstopo | live |
| ch.hiking_network | GeoAdmin layer ch.swisstopo.swisstlm3d-wanderwege | OGD (swissTLM3D free since 2021) | yes, with attribution | no — runtime, cached 30 d by bbox | © swisstopo | yearly |
| ch.closures | GeoAdmin layer ch.astra.wanderland-sperrungen_umleitungen (SwitzerlandMobility via ASTRA) | OGD | yes, with attribution | no — live per audit | © ASTRA / SchweizMobil | daily |
| ch.meteoswiss | MeteoSwiss Open Data (data.geo.admin.ch, ICON-CH forecast, warnings) | OGD (CC-BY-like, attribution) | yes, with attribution | no — live per audit | © MeteoSchweiz | hourly |
| ch.meteoswiss (fallback forecast) | open-meteo.com (ICON model) | CC-BY 4.0 | yes, with attribution | no — live | Weather data by Open-Meteo.com | hourly |
| ch.bafu | GeoAdmin layers ch.bafu.wrz-wildruhezonen_portal, ch.bafu.bundesinventare-*, ch.bafu.waldbrandgefahr | OGD | yes, with attribution | no — cached 30 d (zones), live (fire danger) | © BAFU | zones yearly; fire danger daily |
| ch.guardian_dogs | GeoAdmin layer ch.bafu.herdenschutzhunde (via AGRIDEA) | OGD | yes, with attribution | no — cached 7 d | © BAFU / AGRIDEA | weekly in season |
| ch.army | GeoAdmin layer ch.vbs.schiessanzeigen | OGD | yes, with attribution | no — live per audit (schedules change) | © VBS | daily |
| ch.transport | transport.opendata.ch (Open Data Platform Mobility Switzerland timetable) | Open (OPD Mobility, attribution) | yes, with attribution | no — live per audit | © opendata.ch / SBB | live |
| ch.slf | SLF avalanche bulletin (aws.slf.ch CAAML) | SLF terms (free use, attribution, no interpretation claims) | link/presence only | no — live, presence + level only | © SLF | twice daily in season |
| shared.osm | OpenStreetMap via Overpass API | ODbL 1.0 | yes, ODbL share-alike | no — cached 7 d | © OpenStreetMap contributors | live |
| shared.web | LLM web tool (operator pages, cantonal notices) | per page | quote ≤ 15 words + link only | no | link + quote | live |
| data/famous_routes.yaml | Bergbot-curated seed list (names + official URLs) | MIT (this repo) | yes | yes | — | manual |
| data/cantons.json | Canton codes, names, centroids (derived from swissBOUNDARIES3D, OGD) | OGD | yes, with attribution | yes (tiny derived file) | © swisstopo | yearly |

Decisions: see `docs/decisions/002-static-map-tiles.md` for the tile choice.
