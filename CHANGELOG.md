# Changelog

All notable changes to Bergbot. Milestones follow docs/BERGBOT_WORK_ORDER.md.

## Unreleased

### M0 — Scaffold and guardrails
- Repository layout, `pyproject.toml` (uv, hatchling), `bergbot` console script, ruff/mypy/pytest, GitHub Actions CI.
- `CLAUDE.md`, MIT licence (mascot art excluded), decisions 001–002.
- Adapter contract `sources/base.py` (`fetch`, `freshness`, `licence`, `health`; `Record` with both timestamps).
- Locale loader with completeness check; four packs (ui, warnings, safety, suggestions, playful, report) authored natively.
- Forbidden-vocabulary scanner and tests; i18n completeness and placeholder tests.
- `docs/data-licences.md` matrix; `brand/mascot/{README.md,manifest.json}`; founder art in `brand/mascot/src/`.

### M1 — Domain model and evidence
- `core/domain/models.py`: Place, Route, Difficulty, ConditionSnapshot, Constraint, Amenity, Webcam, Media, Evidence, Warning, Audit, RegisterDecision, ChatMessage, Suggestion, CandidateSet, CheckResult, TransportPlan.
- Invariants in the schema: every Warning has ≥ 1 Evidence; Evidence carries `retrieved_ts` and a ≤ 15-word span; Amenity can only be open/closed with verified evidence; ChatMessage ≤ 12 lines; Audit warnings sorted by severity.
- `bergbot schema export` → `docs/schema/*.json` (17 schemas). Property tests with hypothesis.

### M2 — Source adapters, Switzerland
- 14 adapters behind one contract: `ch.geoadmin` (search, profile, height, canton), `ch.swisstopo_tiles`, `ch.hiking_network` (+ `.wanderland`), `ch.closures`, `ch.meteoswiss` (ICON-CH1/CH2 via Open-Meteo, decision 003), `ch.bafu.quiet_zones`, `ch.bafu.protected_areas`, `ch.bafu.fire`, `ch.guardian_dogs`, `ch.army`, `ch.transport`, `ch.slf`, `shared.osm`; `shared.web` is a specification only.
- `sources/http.py`: httpx fetcher with per-source disk cache and TTL, offline mode, fixture recorder and replayer.
- Recorded fixtures (`tests/fixtures/sources`, 1.6 MB) and contract tests for every adapter; `bergbot doctor` lists health, cache age and licence.
- README and licence row per adapter (`docs/data-licences.md`).

### M3 — Deterministic core
- `core/geospatial`: GPX/KML/GeoJSON parsing, 25 m resampling, LV95 metric ops, polygon/line intersections with km ranges, place resolution (canton hint, municipality preference, coordinates), GPX/KML/GeoJSON export.
- `core/terrain`: swissALTI3D profile via GeoAdmin (POST), ascent/descent with 125 m smoothing and 5 m hysteresis, SAC duration formula, exposure heuristic (class D).
- `core/routing`: identity against SwitzerlandMobility routes (overlap %), network membership, candidate generation from named stages and a trail graph (Dijkstra out-and-back to huts/viewpoints), tiled fetch under GeoAdmin's 200-feature cap.
- `core/conditions`: hourly weather at start/highest/end, wind on exposed segments, thunderstorm/precipitation/heat/cold/snow, fire danger and cantonal fire measures, SLF presence, sunset; zone intersections (closures, diversions, shooting zones, quiet zones with period check, protected areas, guardian dogs) with prefetch for candidate ranking.
- `core/logistics`: nearest stops, outbound and last return via transport.opendata.ch, tight/no-return warnings, OSM amenities capped per kind, lifts/huts always unverified with web-verification specs.
- `core/scoring`, `core/evidence`, `conversation/register.decide()` (rule-based).
- Workflows `run_audit`, `run_find`, `run_around`, `run_check` and CLI commands; five fixture GPX with golden stats; intersection property tests; 20 + 20 register cases; offline end-to-end audits on recorded fixtures.
