# Bergbot — Work Order for Claude Code (Phase 1)

**Read first:** `BERGBOT_PRD.md` (requirements) and `bergbot_product_spec.md` (architecture, all phases). This document tells you *what to build, in what order, and how we know each piece is done*. Requirement IDs (FR-*, NFR-*, SR-*) refer to the PRD.

Work milestone by milestone. Each milestone ends with its acceptance checks green and a short `CHANGELOG.md` entry. Do not start a milestone until the previous one passes. Ask the founder only for the items marked **FOUNDER INPUT**; make every other decision yourself and record it in `docs/decisions/`.

---

## 0. Ground rules

- **Stack:** Python 3.11+, `uv` for env and lockfile, `pyproject.toml`, package name `bergbot`. Geospatial: `shapely`, `pyproj`, `gpxpy`, `geojson`, `rtree`/`shapely.STRtree`. HTTP: `httpx` with on-disk cache (`hishel` or custom). Templates: `jinja2`. CLI: `typer`. Telegram: `python-telegram-bot` (long polling). LLM (standalone modes): `anthropic` SDK with web-search tool. Tests: `pytest`, `pytest-snapshot`, `hypothesis` for geometry. Lint: `ruff`, `mypy --strict` on `core/`.
- **Two execution modes, one codebase.**
  - *Plugin mode* (Claude Code / Claude.ai / bring-your-own channel): the host agent is the LLM. Skills instruct the agent to call the `bergbot` CLI for deterministic steps (`bergbot resolve`, `bergbot audit --json`, `bergbot render`) and to do intent, prose, web verification and media search itself, following the register and locale rules the CLI returns in JSON.
  - *Standalone mode* (CLI chat, Telegram): `bergbot.agent` orchestrates the same steps and calls the Anthropic API with the user's key for the LLM parts.
  Every workflow must be runnable in both modes from the same `core/` code.
- **Determinism boundary:** geometry, distances, intersections, timetables, weather sampling, ranking scores and register selection are computed in `core/`; the LLM never asserts a number `core/` has computed differently.
- **Language-neutral core:** enums and keys in English snake_case; all user-facing strings via `locales/`. Any hardcoded user-facing string fails CI.
- **No "safe":** see forbidden vocabulary test (M6). Write it early, run it always.
- **Mascot placeholders:** build everything with placeholder squares; real art is dropped into `brand/mascot/` later and picked up by the asset pipeline without code changes.
- **Licences:** before bundling any dataset, record it in `docs/data-licences.md` (source, licence, redistribution yes/no, attribution string, update frequency). If redistribution is not clearly allowed, fetch at runtime, never bundle.
- **Commit style:** `feat(core/terrain): …`, `feat(source/ch/meteoswiss): …`, `feat(i18n/fr): …`, `fix(report): …`, `docs(install): …`.
- **Documentation as you go:** every module gets a docstring header explaining its role and boundary; every adapter gets a README with licence and freshness notes.

---

## 1. Repository layout (create in M0)

```
bergbot/
├── README.md  LICENSE  CONTRIBUTING.md  ROADMAP.md  SECURITY.md  CHANGELOG.md  CLAUDE.md
├── pyproject.toml  uv.lock
├── .claude-plugin/marketplace.json
├── plugins/bergbot/                    # the Claude plugin
│   ├── .claude-plugin/plugin.json
│   ├── skills/{audit,find,around,check,export,media,help}/SKILL.md
│   ├── commands/{find,around,audit,check,gpx,help}.md
│   └── agents/{route-investigator,conditions-analyst,logistics-researcher,restriction-researcher,evidence-reviewer,media-scout}.md
├── src/bergbot/
│   ├── cli.py
│   ├── agent/                          # standalone orchestration (Anthropic API)
│   ├── conversation/                   # intent, constraints, register, suggestions, replanning, message renderer
│   ├── core/
│   │   ├── domain/                     # pydantic models (§3)
│   │   ├── geospatial/  terrain/  routing/  conditions/  logistics/  scoring/  evidence/  reporting/
│   ├── sources/
│   │   ├── base.py                     # adapter contract
│   │   ├── ch/{geoadmin,swisstopo_tiles,hiking_network,closures,meteoswiss,bafu,guardian_dogs,army,transport,slf}/
│   │   └── shared/{osm,web}/
│   ├── activities/{hiking,winter_hiking,snowshoe,ski_touring,mtb,trail_running}/   # only hiking implemented in P1; others are stubs with enums
│   ├── adapters/{telegram,cli,channel_passthrough}/
│   └── ui/report/{templates,svg,assets}/
├── locales/{en,fr,de,it}/{ui,warnings,safety,suggestions,playful,report}.yaml
├── brand/mascot/{manifest.json,README.md,src/,dist/}
├── website/                            # static site (Astro or plain HTML+templates), 4 languages
├── docs/{install,connect,decisions,data-licences.md,benchmark/}
├── examples/{glarus-easy-hike,brunnen-around,gpx-audit,dog-day}/
└── tests/{fixtures,source_contracts,geospatial,workflows,safety,register,i18n,report_snapshots,e2e}/
```

---

## 2. Milestones

### M0 — Scaffold and guardrails (Day 1–2)
Tasks
- Create layout above; `pyproject.toml` with `bergbot` console script; `uv` lockfile; `ruff`, `mypy`, `pytest` configured; GitHub Actions CI running lint, type-check, tests on push.
- `CLAUDE.md` at repo root (content in Appendix A).
- `sources/base.py`: `SourceAdapter` protocol — `fetch(query) -> list[Record]`, `freshness() -> Freshness`, `licence() -> Licence`, `health() -> Health`; `Record` carries `source_ts`, `retrieved_ts`.
- Locale loader with completeness check across the four packs (empty packs OK at this stage but keys must match).
- Forbidden-vocabulary test skeleton (`tests/safety/test_forbidden_vocabulary.py`) reading `locales/*/safety.yaml#forbidden` and scanning every rendered string in later milestones.
- `docs/data-licences.md` with empty matrix for every planned adapter.
- `brand/mascot/README.md` (naming convention, formats, sizes) and `manifest.json` with placeholder entries for `default, hike, alpine-hike, ski-tour, trail-run, snowshoe, mtb, climb`.

Accept: `uv run bergbot --help` works; CI green; `uv run pytest` passes with locale-completeness and forbidden-vocab tests present (trivially passing).

### M1 — Domain model and evidence (Day 3–4)
Tasks — `core/domain/` pydantic v2 models:
`Place`, `Route` (geometry LineString WGS84, `segments`, `identity`, `activity`, `difficulty`), `Difficulty` (system enum `sac_t`, grade, source, confidence), `ConditionSnapshot`, `Constraint`, `Amenity` (kind, status `open|closed|unverified|conflicting`, verification), `Webcam`, `Media`, `Evidence` (class `A|B|C|D|E`, source, url, source_ts, retrieved_ts, confidence, original_span ≤ 15 words, translated_summary), `Warning` (type enum, severity `critical|important|note`, evidence list, affected_segment), `Audit`, `RegisterDecision`, `ChatMessage`, `Suggestion`.
- JSON schema export to `docs/schema/` for contributors.
- Property tests: every `Warning` has ≥1 `Evidence`; every `Evidence` has both timestamps.

Accept: `bergbot schema export` writes schemas; tests green.

### M2 — Source adapters, Switzerland (Day 5–12)
Implement each with fixtures (recorded responses), contract test, README, licence row.
1. `ch/geoadmin` — search API (place resolution), elevation profile, layer queries by bbox/geometry.
2. `ch/swisstopo_tiles` — static raster tile fetch and stitch for a bbox (licence check → **record decision**; fallback OSM raster).
3. `ch/hiking_network` — official hiking trail network via GeoAdmin layers; route candidates near a point.
4. `ch/closures` — SwitzerlandMobility/cantonal closure feeds (licence check; runtime fetch).
5. `ch/meteoswiss` — forecast by point/time, wind/gusts, warnings; webcam list (P1).
6. `ch/bafu` — protected areas, wildlife quiet zones, forest-fire danger and restrictions (federal + cantonal where machine-readable; otherwise mark for web verification).
7. `ch/guardian_dogs` — livestock guardian dog areas.
8. `ch/army` — shooting range zones and firing calendar for a date.
9. `ch/transport` — GTFS via Open Data Platform Mobility: nearest stops, journey out/back for a date/time, last return; cableway timetables.
10. `ch/slf` — bulletin presence and danger level by region (presence only, SR-4).
11. `shared/osm` — huts, restaurants, water, shelters, POIs via Overpass; route prominence signal.
12. `shared/web` — *specification only* for LLM web verification: query templates per status type, required output shape (`verified|unverified|conflicting`, url, span, ts). No scraping code.

Cache: static layers on disk with TTL (7–30 d); live per audit. `bergbot doctor` reports each adapter's health and cache age.

Accept: `uv run pytest tests/source_contracts` green offline on fixtures; `bergbot doctor` lists all adapters with health; `docs/data-licences.md` fully populated; every adapter README done.

### M3 — Deterministic core (Day 13–20)
- `geospatial/`: parse GPX/KML/GeoJSON (`gpxpy`, custom KML), simplify/resample (every 25 m), reproject to LV95 for metric ops, `intersect(route, polygons) -> segments with km ranges`, buffer queries.
- `terrain/`: elevation profile from GeoAdmin (fallback: GPX elevations), ascent/descent with noise filter, slope/aspect per segment, exposed-segment heuristic (ridge/steep-side detection from slope + curvature), escape points (nearest trail junctions/stops within X m).
- `routing/`: route identity matching against hiking network (name, overlap %), candidate retrieval for `find`/`around` (network segments → assembled loops/A-to-B between stops), duration via SAC formula with parameters stated in evidence.
- `conditions/`: sample weather along route by hour of the planned window; wind on exposed segments; hazard warnings by bbox; fire danger by polygon; SLF presence.
- `logistics/`: nearest stops to start/end; outbound arriving before planned start; last return after planned end + margin; lift schedules/status → `unverified` unless web-verified.
- `scoring/`: hard constraints filter; soft score (weather, transport fit, ascent fit, difficulty fit); safety findings never in score — they become warnings. Deterministic tie-breaks.
- `evidence/`: attach class/source/timestamps to every output; summary of known/inferred/uncertain/unverified.
- `register.py` (in `conversation/` but rule-based): `decide(audit, intent, question_type) -> RegisterDecision` per FR-R2.
- CLI: `bergbot resolve "<place>" --json`, `bergbot audit <file> --date --json`, `bergbot find --constraints <json> --json`, `bergbot around "<place>" --json`, `bergbot check --kind lift --name … --json`.

Accept: golden tests on 5 fixture GPXs (distance ±1%, ascent ±5% vs reference); intersection tests with synthetic closures; register tests (20 must-be-serious, 20 may-be-playful) green; `bergbot audit examples/gpx-audit/route.gpx --json` produces a valid `Audit`.

### M4 — Report renderer (Day 21–26)
- `ui/report/`: Jinja2 single-file template; CSS inlined; no external requests; no JS required (optional enhancement script inlined and guarded).
- `svg/map.py`: inline SVG with embedded static tile raster (data URI, ≤ 400 KB), route path, severity-coloured hazard segments, markers (start, end, escape, huts, stops, webcams).
- `svg/profile.py`: elevation profile with exposed/hazard segments coloured, km ticks, hut/stop markers.
- Sections exactly per FR-H4; evidence classes A–E badges; footer per FR-H6 with UTM links from `pyproject` config.
- Mascot placement per FR-H9 using `brand/mascot/manifest.json` → variant by activity; placeholder until art exists.
- Asset pipeline `bergbot brand build`: reads `brand/mascot/src/*.{png,svg}`, writes optimised WebP ≤ 40 KB to `dist/`, updates data-URI snippets. **FOUNDER INPUT:** drop art into `brand/mascot/src/` named per README.
- `bergbot render <audit.json> --lang xx --out report.html`; size guard fails > 2 MB, warns > 1 MB.

Accept: snapshot tests per locale; rendered file opens in iOS Files preview with map and profile visible (manual check, record in `docs/decisions/`); size guard green; forbidden-vocab scan of rendered HTML green.

### M5 — Conversation layer (Day 27–33)
- `conversation/intent.py`: prompt + schema for intent and constraint extraction in EN/FR/DE/IT; attachment → `audit`; emergency detection.
- `conversation/suggestions.py`: 4 suggestions from `locales/*/suggestions.yaml` filtered by month and known region.
- `conversation/message.py`: ≤12-line renderer per FR-M1–M3, both registers, four locales; plain text + minimal markdown; closing question logic incl. media offer.
- `conversation/replanning.py`: constraint diff → which core steps rerun.
- `conversation/media.py`: famous-route detection (curated `data/famous_routes.yaml` seed + prominence heuristic) and the web query spec for media links.
- `conversation/qa.py`: answer follow-up questions from `Audit` context first, then general knowledge/web.
- Locale packs: author `playful.yaml` natively per language (short, mountain humour; **FOUNDER INPUT** optional review), `safety.yaml` locked terminology (T1–T6 descriptions, danger levels, closure/fire/shooting wording, the fixed line "Bergbot informs. The decision is yours.").
- Standalone `agent/`: Anthropic API loop with tool schema for the core CLI functions and web search; streaming progress messages every ≤ 20 s.

Accept: 40 intent fixtures (10 per language) ≥ 95% correct; message length test; register + forbidden vocab on messages; e2e in standalone mode: sentence → message + report + gpx on the three canonical prompts in each language.

### M6 — Safety and quality gates (Day 34–36)
- Forbidden vocabulary: full list per locale, scan all rendered outputs and all locale files.
- Safety regressions: fixtures with closure, fire ban, wind on ridge, quiet zone, shooting day, unverified lift → assert warnings present, ordered, serious register, mascot absent from header, fixed line present.
- Unverified never becomes open/closed (test on `Amenity` status transitions).
- Off-network route synthesis forbidden (test that candidate routes are ⊆ network segments).
- Emergency short-circuit test in four languages.
- i18n completeness 100%; report snapshots in four languages.
- Benchmark harness `docs/benchmark/`: 10 real GPX + manual reference findings (**FOUNDER INPUT** for 3–5 routes she knows well; you seed the rest from public well-known routes), `bergbot benchmark` prints pass rate.

Accept: all gates in CI; `bergbot benchmark` runs and publishes a markdown table.

### M7 — Adapters and plugin (Day 37–42)
- Telegram: `bergbot connect telegram` (token prompt, stored in user config, test message), long-polling bot; suggestions as reply keyboard; inline buttons "GPX / Another / Photos"; GPX/HTML as documents; location share → `around`; progress edits. Register rules respected (no mascot sticker/emoji in serious).
- CLI chat: `bergbot chat` REPL with the same behaviour; `/find /around /audit /check /gpx /help`.
- Claude plugin: `.claude-plugin/marketplace.json`, `plugins/bergbot/.claude-plugin/plugin.json`, SKILL.md per workflow describing exactly which `bergbot … --json` commands to run, how to perform web verification and media search (query templates from `shared/web`), how to obey `RegisterDecision` and locale, and how to deliver files. Commands map to skills. Sub-agents per repo layout for parallel research in audit.
- Channel passthrough: docs + e2e fixture showing a message arriving via a generic bridge into Claude Code and files returned.
- Test from a fresh Claude Code: `/plugin marketplace add`, `/plugin install bergbot`, run the three prompts.
- Claude.ai path: attempt install via Customize → Plugins → Add marketplace; record result; website tab "Install" or "Coming soon" accordingly.

Accept: e2e on Telegram (real bot, founder's token) and Claude Code for the three canonical prompts in four languages; files delivered; follow-ups work.

### M8 — Website, docs, launch kit (Day 43–48)
- Static site (four languages, language auto-detect + toggle): Home (mascot hero, real Telegram screenshot, real report, buttons Install · Connect Telegram · ★ Star), Install (tabs: Claude Code, Claude.ai, CLI, Bring-your-own-channel; screenshots per step; copy buttons), Connect (Telegram guide; WhatsApp honest note + beta link), Examples (downloadable real reports), Coverage (adapter health/freshness badges generated from `bergbot doctor --json`), Safety & sources (no mascot), Roadmap, Waitlist (**FOUNDER INPUT**: provider).
- README per FR-I6; CONTRIBUTING with "good first canton/source/language" templates; ROADMAP from spec Phases 2–8; SECURITY.
- Examples folder with real, regenerable outputs (`make examples`).
- Screenshot script to regenerate install guide images.
- Release: PyPI publish workflow, semver tag `v0.1.0`, GitHub release notes.

Accept: PRD §10 definition of done walked end to end by a person who did not build it, in at least two languages; CI green; `v0.1.0` published.

---

## 3. Key interfaces (implement exactly)

```python
# sources/base.py
class SourceAdapter(Protocol):
    id: str            # "ch.meteoswiss"
    def fetch(self, query: Query) -> list[Record]: ...
    def freshness(self) -> Freshness: ...   # source_ts, retrieved_ts, ttl_s
    def licence(self) -> Licence: ...        # name, redistribution: bool, attribution
    def health(self) -> Health: ...          # ok, latency_ms, last_success_ts, note

# conversation/register.py
def decide(audit: Audit | None, intent: Intent, question: QuestionKind) -> RegisterDecision:
    """serious if: any warning severity in {critical, important}; any warning type in
    {closure, fire_restriction, shooting_activity, avalanche_context, exposed_wind};
    question is safety; intent is emergency. Otherwise playful."""

# core/reporting/message.py
def render_message(audit: Audit, register: RegisterDecision, lang: Lang) -> ChatMessage  # ≤ 12 lines
```

`bergbot … --json` commands print a single JSON document to stdout and exit 0; errors go to stderr with exit 2 and a machine-readable `{"error": ..., "unverified": [...]}`.

---

## 4. Locale pack shape

```yaml
# locales/de/safety.yaml
fixed_line: "Bergbot informiert. Die Entscheidung liegt bei dir."
danger_levels: {1: "gering", 2: "mässig", 3: "erheblich", 4: "gross", 5: "sehr gross"}
t_grades:
  T1: "Wandern — …"        # locked, human-reviewed
forbidden: ["sicher (als Urteil)", "unbedenklich", "kein Problem", "kann losgehen"]
warnings:
  trail_closure: {title: "Gesperrter Abschnitt", body: "Offizielle Sperrung zwischen km {from} und {to}."}
```
`playful.yaml` holds greetings, "another one?" variants, empty states, media offers — authored natively. `suggestions.yaml` holds seasonal/regional prompt suggestions.

---

## 5. Mascot asset contract (`brand/mascot/README.md`)

- Source files in `brand/mascot/src/`, named `<variant>.<png|svg>`: `default`, `hike`, `alpine-hike`, `ski-tour`, `trail-run`, and any additional (`snowshoe`, `mtb`, `climb`, `bivouac`, `dog`…).
- Transparent background, ≥ 1024 px on the long side for PNG.
- `bergbot brand build` → `dist/<variant>.webp` (≤ 40 KB, 256 px) and `dist/<variant>.datauri.txt`; also `dist/avatar.png` (512 px) for Telegram.
- `manifest.json` maps `activity → variant` with `default` fallback; edit only this file to change placement.
- Rules enforced in templates: no mascot in `#before-you-go`, none in serious-register messages, none on the Safety page.

---

## 6. Backlog (Phases 2–8, do not start)
Phase 2 hardening/benchmark/cantonal coverage · Phase 3 Bergbot-owned WhatsApp hosted bridge, group mode, richer Telegram UX · Phase 4 local profile + weekend planner · Phase 5 winter (SLF full), MTB, trail running, ChatGPT/Codex/Cursor/Gemini/MCP adapters · Phase 6 adapter SDK, coverage dashboard · Phase 7 business-model validation · Phase 8 country packs FR/IT/AT/DE/SI. Keep enums and folder stubs so these land without refactoring.

---

## Appendix A — `CLAUDE.md` (place at repo root)

```markdown
# Bergbot — instructions for Claude Code working in this repo

You are building Bergbot, an open-source, local-first mountain-planning agent for Switzerland (hiking first),
in EN/FR/DE/IT. Read BERGBOT_PRD.md and BERGBOT_WORK_ORDER.md before any task. Work milestone by milestone.

Rules that override everything else:
1. Never produce, in code, locale files, templates, tests or docs, any phrase telling a user a route or day is
   "safe" (or locale equivalents). Warnings first. End every warnings block with the locale's fixed line.
2. Geometry, distances, intersections, timetables, scores and register selection are computed in src/bergbot/core.
   The LLM explains; it never computes these.
3. All user-facing text comes from locales/{en,fr,de,it}. Four packs must stay identical in keys. No hardcoded strings.
4. The register (playful/serious) is decided by conversation/register.decide(), by rule. Serious means no humour,
   no emoji except 🔴🟠🟡, no mascot.
5. Unverified stays unverified. Never infer open/closed from absence of data.
6. Route candidates are subsets of official/known networks. No off-trail synthesis.
7. Before bundling any dataset, record licence and redistribution in docs/data-licences.md. If unclear, fetch at runtime.
8. Report HTML is single-file, no external requests, no JS required, < 2 MB, readable in iOS static preview.
9. Mascot art lives in brand/mascot; build with placeholders; never place it in or beside warnings.
10. Every adapter: fixtures, contract test, README, licence row. Every milestone: CHANGELOG entry.

Commands: `uv run bergbot --help`, `uv run pytest`, `uv run ruff check`, `uv run mypy src/bergbot/core`.
Ask the founder only for items marked FOUNDER INPUT in the work order. Record all other decisions in docs/decisions/NNN-title.md.
```

## Appendix B — Founder inputs checklist
- [ ] Licence choice (MIT / Apache-2.0)
- [ ] Mascot art files into `brand/mascot/src/` (default, hike, alpine-hike, ski-tour, trail-run, + extras)
- [ ] Mascot name and one-line voice per language (optional for v0.1.0)
- [ ] 3–5 GPX routes you know well, with what you'd expect Bergbot to flag (benchmark seed)
- [ ] Telegram bot token for e2e testing
- [ ] Waitlist provider / form
- [ ] GitHub org, package name, domain
- [ ] Review of FR/DE/IT playful strings (optional)
