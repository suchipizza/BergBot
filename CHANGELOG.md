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

### M4 — Report renderer
- Single-file HTML report (`ui/report/templates/report.html.j2`): inline CSS, no JS, no external requests, sections Before you go → Route → Conditions → Terrain → Logistics → Around → Photos & stories → Evidence → Footer.
- Inline SVG map with embedded swisstopo raster (data URI, ≤ 400 KB), route, severity-coloured segments, start/end/escape/hut/lift markers, scale bar; inline SVG elevation profile with coloured segments and km ticks.
- Evidence badges A–E on every finding, verbatim source text beside the translation, `Bergbot informs. The decision is yours.` closes the warnings block.
- Mascot pipeline `bergbot brand build` (background removal, WebP ≤ 40 KB, 512 px PNG, avatar); header mascot only in playful register and never with a critical warning; footer mascot always; never inside the warnings block.
- `bergbot render` with 1 MB warning / 2 MB fail; snapshot tests per locale, forbidden-vocabulary scan of rendered HTML, self-containment test.

### M5 — Conversation layer
- `conversation/intent.py`: rule-based intent + constraint extraction in EN/FR/DE/IT (dates, cantons, places, ascent, distance, travel time and origin, T-grade, hut/dog/kids/loop…), emergency short-circuit, attachment → audit; LLM schema/prompt for refinement.
- `conversation/suggestions.py` (seasonal, regional), `message.py` (≤ 12 lines, fixed order, both registers, folded extra warnings, closing question with media offer), `replanning.py` (constraint diff → steps; relative modifiers), `media.py` (curated `data/famous_routes.yaml` + prominence), `qa.py` (answers from audit context; safety frame).
- `agent/`: `Session` (deterministic orchestration, files in workdir, register applied by rule) and `LLM` (Anthropic API: structured intent refinement, web verification returning `WebVerification`, media links, free chat within register). Works without a key (deterministic mode).
- `bergbot chat` REPL with optional slash commands; canton centroids `data/cantons.json` anchor `find`.
- Tests: 40 intent fixtures (100 %), message shape/register/forbidden vocabulary, session e2e on recorded fixtures for the three canonical prompts in four languages, emergency and help.

### M6 — Safety and quality gates
- Safety regressions (closure, fire ban, wind on ridge, quiet zone, shooting day, unverified lift) in four languages: warnings present and ordered, serious register, no header mascot, fixed line; warnings survive constraints; unverified never becomes open/closed (schema, OSM, LLM verification guard); emergency short-circuit through the session in four languages.
- Off-network synthesis test: every graph candidate vertex within 30 m of the official network; named candidates come from the SwitzerlandMobility layer.
- Benchmark harness `bergbot benchmark` (10 real routes, `docs/benchmark/`), offline replay in CI, 10/10 pass on the recording date; network-membership fetch tiled along the route.
- Packaging: hatch build hook copies locales, brand and seed data into the wheel (`bergbot/_data`); editable installs no longer shadowed.
