# Bergbot
## Product & Architecture Specification — open-source mountain intelligence for AI agents

**Status:** Pre-build specification (supersedes the MountainGraph working draft of 8 Sept 2026)
**Date:** 8 September 2026
**Name:** Bergbot (mascot: provided by founder, name TBD)
**Tagline:** *Check everything before you go to the mountains.*
**Consumer line:** *Tell Bergbot where you want to go. It checks the weather, the trail, the hazards, the train — and hands you the route.*
**Geography:** Switzerland first, Alps next
**Languages:** English, French, German, Italian — equal footing, from day one
**Interfaces (Phase 1):** Telegram, Claude Code, Claude.ai (plugin), CLI
**Interfaces (later):** WhatsApp, ChatGPT/Codex, Cursor, Gemini, MCP, hosted app
**Navigation handoff:** GPX/KML → swisstopo app (also Komoot/Gaia/any GPX reader)
**Phase 1 goal:** GitHub stars + waitlist, driven by shared audits
**Licence:** permissive open source (MIT or Apache-2.0, decide before launch)

---

## 0. Changes versus the MountainGraph draft

| Topic | Draft | This spec |
|---|---|---|
| Name | MountainGraph (codename) | Bergbot |
| Primary surface | Claude Code skill | Chat (Telegram first) and Claude Code, equal weight |
| Audience | Technical user first, public in Phase 3 | General public and professionals from Phase 1 |
| Interaction | Slash commands | Natural-language chatbot; slash commands optional |
| Phase 1 scope | Audit only | Full operational product: audit + find + around + chat + report + GPX + messaging + i18n |
| Report | Local HTML, hosted page considered | Single self-contained HTML shared through chat; no extra webpage |
| Personality | Not specified | Playful *and* serious; strictly serious on safety; mascot |
| New feature | — | Famous-route media lookup (photos, articles, reports) |
| New feature | — | Suggested prompts when the user doesn't know what to ask |
| WhatsApp | Own adapter | Works through the user's already-connected agent (Phase 1); Bergbot-owned bot only as hosted beta (Phase 3) |
| Install | Skill files | Plugin marketplace (`.claude-plugin/marketplace.json`) + visual install guides per surface |

---

# Part I — Product

## 1. What Bergbot is

Bergbot is an open-source mountain-planning agent. You give it a place, a wish ("easy hike tomorrow, canton Glarus, under 500 m up") or a GPX file. It gathers official Swiss data and current web information, checks everything that can change your day, tells you the dangers and unknowns first, recommends suitable routes, produces a mobile HTML briefing with evidence, and hands you a GPX ready for swisstopo.

It runs on the user's own AI subscription and machine. Bergbot the company pays nothing per audit, so the free product can be excellent without limits.

Bergbot is **not**: a map app, a swisstopo clone, a Komoot competitor, a generic Swiss open-data MCP, or a tool that declares routes "safe".

## 2. Goals

**Phase 1 (launch):**
1. GitHub stars — the repository people send when someone asks "can an AI plan a mountain day better than checking six apps?"
2. Waitlist — collected from the footer of every shared report and from the website.
3. Real usage — audits run, reports shared, GPXs exported.

**Long term:** the agent-native layer for mountain activity planning across the Alps; business model deliberately open (see §26). The free product must remain worth starring even if a paid product never exists.

## 3. Who it is for

Both audiences from day one, same product, one interface:

**General public**
- Day hiker who currently checks SBB, MeteoSwiss, swisstopo and a hut website separately, or checks nothing.
- Family / group organiser who needs "something everyone can do, reachable by train".
- Dog owner (guardian-dog zones, wildlife zones, hut rules).
- Bivouac / overnight planner (where is it legal, is there a fire ban).
- Visitor to Switzerland who doesn't know the regions, the T-scale or the apps.

**Professionals and experienced users**
- Mountain guides, hut wardens, outdoor-programme leaders: fast pre-brief of a known route, with sources.
- Ski tourers / snowshoers (from Phase 4): bulletin, slope, aspect, elevation context.
- Trail runners, MTB riders (from Phase 4/5).
- Developers and agent power users: install in Claude Code, extend adapters, add cantons.

The same message satisfies both: the public reads the first five lines, the professional opens the report and the sources.

## 4. Product principles

1. **Warnings before beauty.** Dangers, closures and unknowns first; photos and elevation profiles after.
2. **Evidence before confidence.** Every claim carries source, source timestamp, retrieval timestamp and confidence.
3. **Never "safe".** Absence of a warning is never presented as safety. Bergbot informs; the user decides.
4. **Simple to the point of obvious.** No syntax, no commands required, no settings screen. A first-time user succeeds on the first message.
5. **Public and professional in one voice.** Plain language on top, depth underneath.
6. **Aha in the first reply.** The first answer must already feel like an expert did an hour of work.
7. **Shareable by default.** Every output is designed to be forwarded to a friend who has never heard of Bergbot.
8. **Local and open.** Execution on the user's machine, user's LLM, official/open data, live web verification. Nothing phoned home.
9. **Multilingual from the schema up.** Language-neutral keys, localised presentation, reviewed safety terminology.
10. **Commerce never touches safety.** Any future commercial placement is labelled and can never alter warnings or ranking.
11. **Deterministic geometry, LLM interpretation.** Distances, intersections, elevation and timetables are computed; the model explains, ranks and converses.
12. **Portable.** Claude is the first surface, not the product. No "Claude" in the brand or the core.

## 5. Personality

Bergbot has two registers and switches between them deterministically.

**Playful (default)** — warm, short, a bit of mountain humour, mascot present. Used for: greetings, suggestions, discovery, photos, "another one?", small talk, empty states, errors that are not safety-related.

> "Glarus with under 500 m of climbing — there are more of those than people think. Three ideas, sorted by tomorrow's weather 👇"

**Serious (safety mode)** — precise, no jokes, no emoji beyond the severity markers, no mascot. Triggered automatically whenever the message contains a red or orange warning, avalanche context, closure, fire restriction, shooting-range activity, wind on exposed terrain, or when the user asks a safety question ("is it dangerous?", "can I take kids?", "is the snow gone?").

> "⚠ Before you go — the official closure layer marks the section between km 7.2 and 8.6 as closed (Canton Uri, updated yesterday). I have no verified detour. Two alternatives below."

Rules:
- Safety mode is entered by rule, not by model mood. The renderer decides based on the audit's severity, then the model writes within that register.
- Bergbot never softens, jokes about, or buries a warning. Never says "should be fine", "probably safe", "go for it".
- Bergbot answers "is it safe?" with what is known, what is unknown, and a statement that the decision is the user's.
- Emergency questions ("someone fell") → immediately: 1414 (Rega) / 112, position sharing advice, no other content.

**Mascot**
- Provided by founder. Used as: chat avatar, report header, empty states, suggestion cards, website hero, README.
- Never appears inside or next to the warnings block, and never in safety-mode messages.
- Ships in the repo as SVG in `brand/` with usage guidelines; contributors may not alter it.

## 6. The user experience

### 6.1 Discovery
Website or repository, in the visitor's language (auto-detect + toggle EN/FR/DE/IT). Above the fold: one line of promise, one real Telegram screenshot, the HTML report it produced, three buttons — **Install · Connect Telegram · ★ Star**. Waitlist link in the footer.

### 6.2 Install
A tabbed install page, one tab per surface, each with a three-step visual guide (one screenshot per step, one copy button per command), available in all four languages.

- **Claude Code** — `/plugin marketplace add <org>/bergbot` then `/plugin install bergbot`. The repo is a plugin marketplace from day one (`.claude-plugin/marketplace.json`).
- **Claude.ai** — Customize → Plugins → Add marketplace → repo URL. *Verify this path against current Claude.ai behaviour before writing the guide; if unsupported at launch, the tab reads "coming soon" rather than shipping a broken instruction.*
- **ChatGPT / Codex** — same pattern, same verification caveat (Phase 5).
- **CLI** — `pipx install bergbot` (or `npx bergbot`), then `bergbot chat`.
- **Telegram** — separate "Connect messaging" guide: create bot via BotFather (30 s), paste token into `bergbot connect telegram`, Bergbot runs a local poller. Fully local-first, nothing to host.
- **Bring your own channel (WhatsApp, Signal, iMessage, …)** — if the user's agent (Claude Code or any personal agent gateway) is already connected to a messaging app through an MCP server or bridge, Bergbot needs no adapter at all: install the plugin, message the agent from WhatsApp, Bergbot replies through the same channel with report and GPX. Phase 1, zero extra wiring. Bergbot documents compatibility but does not ship, recommend or maintain any bridge, and states that unofficial WhatsApp Web bridges breach WhatsApp's terms and can get a number banned.
- **WhatsApp — Bergbot-owned bot** — for users with no agent of their own. The Business API requires a Meta business account, a dedicated number and a public webhook, so this is a hosted beta run by Bergbot (Phase 3), with a self-host guide for the technically able.

### 6.3 First message
The user writes in any of the four languages, in their own words. Three intents are recognised:

| Intent | Example | Internal workflow |
|---|---|---|
| **Find** | "Generate a hike for tomorrow with less than 500 m up in canton Glarus" | `find` |
| **Around** | "Can you find a hike near Brunnen?" | `around` |
| **Audit** | "Check if this hike is good today" + GPX attached | `audit` |

Also recognised: **check** ("is the Gemmi gondola running Sunday?"), **weekend** ("what should I do this weekend?", Phase 4), **export** ("send me the GPX"), and free conversation.

Slash forms (`/find`, `/around`, `/audit`, `/weekend`, `/check`, `/gpx`) exist for Claude Code and CLI power users. They are never required.

**If the user doesn't know what to ask**, Bergbot offers suggestions. Triggered by: first contact, "hi", "what can you do?", an empty or vague message, or five seconds of silence in a UI that supports it. Suggestions are concrete, localised to the user's language and, when known, their region and the season:

> "Not sure where to start? Try one of these:
> • *Easy hike tomorrow, under 2 h from Zürich by train*
> • *Something with a hut lunch near Engelberg*
> • *Is the Hardergrat doable this weekend?*
> • *Send me a GPX and I'll check it*"

In Telegram these are tappable keyboard buttons; in Claude Code and CLI they are numbered.

### 6.4 The reply
One message, ≤ 12 lines, fixed order:

1. ⚠ warnings — only if any; 🔴 critical / 🟠 important / 🟡 note.
2. Recommended route: name · T-grade · distance · ascent · duration · start/end stop.
3. Weather line for the route and time window.
4. Transport line (outbound and last return).
5. One "why this one" sentence.
6. Attachment: `bergbot-report.html`.
7. Closing question: **"Want the GPX, another suggestion, or photos of this route?"**

For `find`, two or three candidates of two lines each, then the same closing question. For `audit`, the warnings block is followed by the verdict-free summary ("here is what I found; here is what I couldn't verify") and the report.

Everything else lives in the report. The message is the first aha; the report is the second.

### 6.5 Famous-route media lookup (new)
When the recommended or audited route is recognised as well-known (a name match against a curated list, high OSM/SwitzerlandMobility prominence, or many web results), Bergbot adds to the closing question: *"…or photos and stories about this route?"* On request it searches the web and returns 3–5 links with one-line descriptions: official route page, a photo gallery, a recent trip report, a video. Rules: links only, never re-hosted images; dated; clearly marked as third-party and not part of the safety audit; skipped entirely in safety-mode replies until the user asks.

### 6.6 Conversation
Bergbot is a real chatbot. After the first reply the user can ask anything and Bergbot answers from the audit context, its data and the web:

- Follow-ups: "shorter", "with a hut", "Sunday instead", "start from the other side", "is there water on the way?", "can my 8-year-old do this?", "what's T3 actually?"
- Explanations: what a T-grade means, how to read the avalanche bulletin, what the fire ban covers, how to import into swisstopo.
- Comparisons: "which of the three has the best view?", "which is quieter?"
- General mountain questions unrelated to a route.

Each follow-up that changes the plan re-runs the affected checks and updates the report. Conversation history lives in the chat thread (Telegram) or session (Claude Code); no server-side memory.

### 6.7 Export
"GPX" → the file arrives in the thread plus one line: *"Open in swisstopo → Import."* KML and GeoJSON on request. In Claude Code/CLI the files land in the working directory with paths printed.

### 6.8 Share
The user forwards the chat message and the HTML file. The recipient gets the same five-second warnings-first experience without installing anything, then sees the footer: **★ Star on GitHub · Install Bergbot · Join the waitlist**. This is the acquisition loop. No hosted page; Phase 1 therefore measures stars, installs and waitlist signups, not opens.

### 6.9 Claude Code / CLI experience
Identical content, different container: install plugin → type the same sentence (or `/find …`) → same ≤12-line reply in the terminal → `report.html`, `route.gpx` written locally → same follow-up conversation. Suggested prompts appear on `/bergbot` or on an empty prompt.

## 7. The HTML report

A single self-contained `.html` file per audit. This is the product's most-seen surface.

**Constraints**
- Opened from a chat attachment on iOS it renders in a static preview: **no JavaScript, no network**. Therefore everything is pre-rendered into the file: inline SVG map with route line and hazard markers over an embedded static tile image, inline SVG elevation profile, webcam thumbnails embedded as data URIs (small), no external fonts.
- Progressive enhancement: if JS is available (Android, desktop), the map becomes pannable and links open in-app. Nothing essential depends on it.
- Target < 2 MB so it forwards without WhatsApp/Telegram compression issues.
- Language of the report = language of the conversation; a language switch is a set of four pre-rendered files only when requested.

**Structure (top to bottom)**
1. ⚠ Before you go — warnings, severity-coloured, each with source + timestamp. No mascot, no CTA here.
2. Route card — name, T-grade with one-line explanation, distance, ascent/descent, duration, start/end, map.
3. Conditions — weather along route by hour, wind on exposed sections, snow/avalanche context when relevant, fire danger.
4. Terrain — elevation profile, exposure segments, escape points.
5. Logistics — transport out and back with times, lifts with operating status and verification state, huts/restaurants with open/unverified flag.
6. Around — webcams, water, shelters, camping/bivouac/dog rules where verifiable.
7. Photos & stories — the media links from §6.5, when requested.
8. Evidence — what is official, derived, forecast, interpreted, or requires personal judgment (see §22); source list with timestamps.
9. Footer — mascot, "Made with Bergbot", ★ Star · Install · Join waitlist.

## 8. Features by workflow (Phase 1 unless marked)

**Audit** — route identity and geometry; distance/ascent/descent/duration; activity type; SAC T1–T6 where available; terrain, altitude, slope, aspect; closures and diversions; weather along route; wind and gusts on exposed sections; natural-hazard alerts; forest-fire danger and restrictions; wildlife quiet zones and protected areas; shooting-range zones and firing schedules; livestock guardian dogs; public transport out and back; cableway schedules and status; huts/restaurants and verification status; webcams; camping/bivouac/fire/dog rules; water, shelters, POIs; escape points; known/inferred/uncertain/unverified; sources and confidence.
**Find** — natural-language constraints (region, distance, travel time, ascent, duration, difficulty, weather, hut, water, dog, bivouac, transport), candidate retrieval, condition-based ranking, 2–3 options, then audit of the chosen one.
**Around** — any place input (address, village, stop, lift station, hut, summit, coordinates, GPX) → suitable activities nearby, ranked.
**Check** — one-question status checks: lift running, hut open, road/pass open, fire ban.
**Export** — GPX/KML/GeoJSON.
**Suggest** — prompt suggestions (§6.3).
**Media** — famous-route photos/stories (§6.5).
**Chat** — free conversation on any of the above.
**Weekend** (Phase 4) — "what should I do this weekend?" with local preferences and multi-area weather.
**Winter** (Phase 5) — SLF bulletin context, snowshoe and ski-touring routes, discipline scales.
**Other activities** (Phase 5+) — MTB, trail running, via ferrata, climbing, alpine routes.

---

# Part II — Architecture

## 9. System overview

```
┌──────────────── Surfaces ────────────────┐
│ Telegram │ Claude Code │ Claude.ai │ CLI │ (later: WhatsApp, ChatGPT/Codex, Cursor, Gemini, MCP, hosted app)
└────┬──────────┬───────────┬─────────┬────┘
     ▼          ▼           ▼         ▼
┌──────────── Layer 3: Agent adapters ────────────┐   thin: I/O, auth, attachments, buttons
└───────────────────────┬─────────────────────────┘
                        ▼
┌──────────── Layer 2: Conversation & workflows ──┐   intent detection, register (playful/safety),
│ audit · find · around · check · weekend · media │   suggestion engine, replanning, i18n rendering
└───────────────────────┬─────────────────────────┘
                        ▼
┌──────────── Layer 1: Deterministic core ────────┐   place, route, terrain, intersections,
│ geospatial · terrain · conditions · logistics   │   conditions, scoring, evidence, report render
└───────────────────────┬─────────────────────────┘
                        ▼
┌──────────── Layer 0: Source adapters ───────────┐   per country / canton / operator;
│ ch/ (geoadmin, meteoswiss, slf, transport, …)   │   contract-tested; freshness-tracked;
│ shared/ (osm, web verification)                 │   live web via the user's agent
└─────────────────────────────────────────────────┘
```

The LLM (user's subscription) sits in Layer 2: it detects intent, extracts constraints, writes prose in the required register and language, performs web verification and media search, and explains. It never computes geometry, distances, intersections or timetables; Layer 1 does, and passes structured results to the model.

## 10. Layer 0 — Source adapters

Each adapter implements one contract:

```
fetch(query) -> Records[]      # normalised to domain schema
freshness() -> {source_ts, retrieved_ts, ttl}
licence() -> {name, redistribution, attribution}
health() -> {ok, latency, last_success}
```

**Swiss adapters, Phase 1**
- GeoAdmin / swisstopo — search, elevation profile, hiking network, map tiles for static rendering.
- Hiking closures — SwitzerlandMobility / cantonal feeds (licence check required).
- MeteoSwiss Open Data — forecast, wind, warnings; official webcams.
- BAFU / cantons — protected areas, wildlife quiet zones, forest-fire danger and restrictions.
- Livestock guardian dog dataset.
- Swiss Armed Forces — shooting range zones and firing calendar.
- Open Data Platform Mobility Switzerland — GTFS timetables, cableway/lift schedules.
- OSM — huts, restaurants, water, shelters, POIs, route prominence.
- Web verification (via agent) — operator pages for lift status, hut opening, cantonal fire bans, recent trip reports, media.

**Phase 4/5:** SLF avalanche bulletin API, snow depth, winter route sources.
**Phase 8:** country packs `fr/ it/ at/ de/ si/` following the same contracts; no Swiss source name in the core model.

Every adapter ships with fixtures, a contract test, a licence file and a freshness badge on the coverage page.

## 11. Layer 1 — Deterministic core

- **Place resolution** — text/coordinates/stop/hut/summit → canonical place with bbox, canton, elevation.
- **Route ingestion** — GPX/KML/GeoJSON parse, simplify, resample, identify against known routes.
- **Route discovery** — candidate routes near a place or matching constraints, from official network + OSM.
- **Terrain** — elevation profile, slope, aspect, exposure segments, escape points.
- **Spatial intersections** — route × closures, protected areas, quiet zones, guardian-dog areas, shooting zones, fire-danger polygons.
- **Conditions** — weather sampled along route by time window, wind on exposed segments, hazard alerts, snow/avalanche context.
- **Logistics** — reachability and return options via GTFS, lift schedules and status, hut/restaurant status.
- **Scoring** — constraint satisfaction and ranking; safety findings are hard filters or top-ranked warnings, never trade-offs.
- **Evidence** — every finding tagged with class (§22), source, timestamps, confidence.
- **Personalization** (Phase 4) — local profile file, selected/rejected history.
- **Reporting** — `audit.json` → `report.html` (four locales), `route.gpx/kml/geojson`, chat message (≤12 lines).

## 12. Layer 2 — Conversation & workflows

- **Intent detection** — find / around / audit / check / weekend / export / media / chat / help, from natural language in EN/FR/DE/IT; attachments imply audit.
- **Constraint extraction** — region, time, ascent, duration, difficulty, transport, hut, water, dog, bivouac, group → structured `Constraint`.
- **Register controller** — sets playful or safety register from audit severity and question type (§5); the model writes within it.
- **Suggestion engine** — localised, seasonal, region-aware prompt suggestions on first contact, vague input or help.
- **Media lookup** — famous-route detection → web search → 3–5 dated links.
- **Replanning** — follow-ups mutate constraints, rerun affected core steps, regenerate report.
- **Localisation** — language-neutral keys → reviewed strings; source-language content kept alongside translated summary.
- **Workflows** — `audit`, `find`, `around`, `check`, `weekend`, `export`, defined once, reused by every adapter.

## 13. Layer 3 — Agent adapters

Thin adapters only: authentication, message in/out, attachments, buttons/keyboards, file delivery.

- `telegram/` — local long-polling bot; token from BotFather; inline keyboards for suggestions and "GPX / another / photos".
- `claude/` — plugin (marketplace.json, skill files, slash commands); works in Claude Code and Claude.ai.
- `cli/` — `bergbot chat`, `bergbot audit <gpx>`, `bergbot find "<text>"`.
- `channel-passthrough/` — no code: any messaging channel already wired into the host agent reaches Bergbot through the `claude/` plugin; report and GPX are returned as files in that channel. Tested against common WhatsApp/Signal MCP bridges in CI fixtures.
- `whatsapp/` (Phase 3) — Cloud API bridge for users without an agent; hosted by Bergbot for beta users, self-host guide for others.
- `codex/ chatgpt/ cursor/ gemini/ mcp/` (Phase 5) — same workflows, surface-specific packaging.

## 14. Data model (language-neutral)

`Place` · `Route` (geometry, identity, activity, difficulty, segments) · `Difficulty` (system, grade, source, confidence) · `ConditionSnapshot` (weather, wind, hazards, snow, fire, time window) · `Constraint` · `Amenity` (hut, restaurant, lift, water, shelter; status + verification) · `Webcam` · `Media` (title, url, type, date) · `Evidence` (class, source, source_ts, retrieved_ts, confidence, original span, translated summary) · `Warning` (type, severity, evidence, affected segment) · `Audit` (route, warnings, conditions, logistics, amenities, evidence, media, locale) · `Profile` (Phase 4, local file).

Warning types and severities are enums; presentation strings live in `locales/`.

## 15. Repository

```
bergbot/
├── README.md (EN, links FR/DE/IT)  LICENSE  CONTRIBUTING.md  ROADMAP.md  SECURITY.md
├── .claude-plugin/marketplace.json
├── brand/                     mascot SVGs, usage guide
├── skills/                    audit · find · around · check · weekend · export · help
├── agents/                    route-investigator · conditions-analyst · logistics-researcher · restriction-researcher · evidence-reviewer · media-scout
├── core/                      domain · evidence · geospatial · routing · terrain · conditions · scoring · personalization · reporting · conversation
├── sources/ch/ …  sources/shared/{osm,web}
├── activities/                hiking · winter-hiking · snowshoe · ski-touring · mtb · trail-running
├── adapters/                  telegram · claude · cli · whatsapp · later/{codex,chatgpt,cursor,gemini,mcp}
├── ui/report/                 templates, inline-svg map & profile renderers, i18n
├── locales/{en,fr,de,it}/     ui, warnings, safety-terminology (reviewed), suggestions
├── website/                   four-language static site, install guides with screenshots
├── examples/                  glarus-easy-hike · brunnen-around · gpx-audit · dog-weekend
└── tests/                     fixtures · source-contracts · geospatial · safety-regressions · register-tests · report-snapshots · i18n-completeness
```

## 16. Multilingual architecture

- Internal keys neutral (`warning_type: trail_closure`, `severity: critical`).
- Four locale packs with equal completeness enforced by CI (`i18n-completeness` test fails the build on a missing key).
- Safety terminology (closures, avalanche danger levels, fire bans, T-scale descriptions) is human-reviewed per language and locked; the LLM may not paraphrase these strings.
- Source-language content (e.g. German cantonal notice for a French user) is kept verbatim alongside the translated summary and the link.
- Reply language = user's message language; report language follows; README/website in all four.
- Playful register is localised, not translated: humour is written natively per language.

## 17. Safety architecture

Output classes, visible in the report and enforced in the schema:
- **A. Official fact** — "the official closure layer marks this section closed."
- **B. Derived fact** — "the GPX intersects the closure for ~1.4 km."
- **C. Forecast** — "MeteoSwiss forecasts gusts of 55–70 km/h at 13:00 in the route area."
- **D. Interpretation** — "relevant because the route spends ~35 min on an exposed ridge."
- **E. Judgment required** — "whether your group should continue cannot be established by this tool."

Rules enforced in code and tests:
- Safety findings cannot be filtered out by constraints, personalization or ranking.
- No "safe" vocabulary in any locale (`safety-regressions` tests grep rendered output).
- Unverified status is displayed as unverified, never as open/closed.
- Avalanche context is contextualised, never reduced to go/no-go.
- Route generation stays on official/known networks; no off-trail synthesis.
- Emergency intent short-circuits everything to 1414/112 guidance.
- Register controller forces safety mode on any red/orange finding; mascot and humour are suppressed by the renderer, not by prompt politeness.

## 18. Privacy and execution

Local-first: user's machine, user's LLM key/subscription, user's Telegram bot. No Bergbot server in Phase 1 except the static website and the waitlist form. GPX files, preferences and history stay local. The report footer links contain no tracking beyond a UTM source. Phase 3 hosted WhatsApp bridge is opt-in beta with a published data policy.

## 19. Distribution and star mechanics

- Plugin marketplace install in one command; Telegram connect in under two minutes.
- Install guides with screenshots in four languages.
- README opens with a Telegram screenshot and the report; three copy-paste example prompts per language.
- Every report footer: ★ Star · Install · Waitlist.
- Coverage page with source-health and freshness badges.
- "Good first canton / source / activity / language" issues.
- Public roadmap (§25).

## 20. Website

Static, four languages, no backend beyond the waitlist form. Pages: Home · Install (tabs per surface) · Connect Telegram/WhatsApp · Examples (real reports, downloadable) · Coverage · Safety & sources · Roadmap · Waitlist · GitHub. The mascot appears on Home and Install; never on Safety.

## 21. Waitlist

Footer and website. Asks: email, language, region, activities, "what would you want Bergbot to do that it can't yet?", interest in WhatsApp beta / hosted app / monitoring / guides & huts. Used only to learn; no promise of a paid product.

---

# Part III — Roadmap

Phase 1 ships a complete, daily-usable product. Later phases extend, they do not complete.

## Phase 1 — Full operational launch (Switzerland, hiking)
Deliver: public repo as plugin marketplace · Telegram adapter (local) · Claude Code + Claude.ai plugin · bring-your-own-channel support (WhatsApp etc. via the user's existing agent bridge) · CLI · `find`, `around`, `audit`, `check`, `export`, `help/suggest`, free chat · famous-route media lookup · playful/safety register with mascot · Swiss adapters listed in §10 · deterministic core §11 · self-contained mobile HTML report (iOS-static-safe) · GPX/KML/GeoJSON · swisstopo handoff guide · full EN/FR/DE/IT · four-language website with visual install guides · waitlist · examples · tests (contracts, safety, register, i18n).
Success: a non-technical person connects Telegram in under five minutes, writes one sentence in their language, receives a warnings-first recommendation and report, forwards it, and the recipient can act on it without installing anything; a developer installs the plugin in one command and gets the same. Metrics: stars, installs, audits, exports, waitlist signups.

## Phase 2 — Hardening and coverage
Deliver: gold-standard benchmark (manually verified real routes, hard cases with closures, fire bans, wind, quiet zones, ambiguous operator status) · cantonal closure/fire adapters for all cantons · webcam matching quality · hut/lift verifier improvements · report performance on old phones · localisation review by native speakers · suggestion engine tuned by season and region.
Success: benchmark pass rate published; zero safety-regression failures across four languages.

## Phase 3 — Messaging expansion
Deliver: WhatsApp via hosted beta bridge and self-host guide · richer Telegram UX (inline buttons for follow-ups, location sharing as `around` input) · group-chat mode (one Bergbot in a friends' group) · conversational replanning polish.
Success: a WhatsApp-only user completes find → report → GPX without touching GitHub.

## Phase 4 — Personalization and weekend planning
Deliver: local profile (fitness, preferences, home stop, dog, kids) · `weekend` workflow with multi-area weather · selected/rejected history · recommendation explanations ("because you liked…") · all local, exportable, deletable.
Success: a repeat user asks "what should I do this weekend?" and gets suggestions that match their habits.

## Phase 5 — Winter and more activities, more agents
Deliver: SLF bulletin integration, slope/aspect/elevation matching, snowshoe and ski-touring routes, discipline scales, stricter winter safety wording and tests · MTB and trail running · ChatGPT/Codex, Cursor, Gemini, MCP adapters with the same install-guide standard.
Success: a ski tourer gets bulletin-contextualised audit; the plugin installs on at least three non-Claude agents.

## Phase 6 — Contribution ecosystem
Deliver: source adapter SDK · coverage dashboard · freshness/health CI · fixtures generator · contributor docs in four languages · "good first" issue programme.
Success: meaningful adapter or region contributed by someone outside the core team.

## Phase 7 — Business-model validation (no SaaS build)
Use waitlist segmentation and usage to test: hosted app / WhatsApp convenience · continuous monitoring ("tell me when the Gemmi lift reopens") · proprietary history/outcome data · guide/hut/operator marketplace around live demand · B2B/API for tourism boards and operators. Choose, or choose not to monetise. Free product untouched in every scenario.

## Phase 8 — Alps and beyond
Deliver: country packs FR, IT, AT, DE, SI on the same adapter contracts; national difficulty scales; navigation handoff to local reference apps; additional languages only when a country pack lands.
Success: a French user audits a Chamonix route with French official sources and the same experience.

---

# Part IV — Measures, risks, decisions

## 22. Metrics
Open source: stars, forks, installs per surface, contributors. Usage: audits, finds, exports, media lookups, follow-up depth, Telegram connections. Quality: benchmark pass rate, source freshness, safety-regression count, i18n completeness. Distribution: waitlist signups by footer vs website, language and region mix. Business (Phase 7): interest by hypothesis.

## 23. Risks and mitigations
- **False sense of safety** → output classes, no "safe" vocabulary, safety-mode register, tests.
- **Web verification hallucinates opening status** → status shown as verified/unverified with timestamp; never inferred from silence.
- **iOS static preview breaks the report** → pre-rendered SVG/static images; snapshot tests on iOS.
- **WhatsApp friction contradicts "easy"** → bring-your-own-channel for users with a connected agent (Phase 1); Telegram for everyone else; hosted Business API bridge in Phase 3. Bergbot never depends on, or ships, an unofficial WhatsApp bridge.
- **Claude.ai plugin path differs from assumption** → verify before publishing the guide; "coming soon" fallback.
- **Source licensing blocks redistribution** → licence matrix per adapter before launch; fetch-at-runtime where redistribution is not allowed.
- **Government APIs change** → contract tests, health badges, graceful "could not verify" degradation.
- **Playfulness leaks into safety** → register decided by renderer rule, tested.
- **Scope too broad** → hiking first; activities and countries are packs behind the same contracts.
- **Incumbents add AI** → open, local, sourced, multilingual, chat-native; differentiation is the audit rigour and the share loop.
- **Messaging platform dependency** → workflows are surface-agnostic; Telegram and Claude Code both first-class.

## 24. Definition of done — Phase 1
A first-time user, in any of the four languages, can: install (Claude Code, Claude.ai or CLI) or connect Telegram from a visual guide · receive prompt suggestions · ask for a hike by constraints, near a place, or by GPX · receive a ≤12-line warnings-first answer with weather, difficulty, transport and a self-contained mobile report · ask follow-up questions and get real answers · request photos/stories for a famous route · receive GPX/KML in the chat and import into swisstopo · forward message and report to a friend who can act on them · see and use ★ Star / Install / Waitlist in the footer · inspect every source and the code. Bergbot is playful when it can be and serious when it must be, and never says a route is safe.

## 25. Decisions still open
1. Licence (MIT vs Apache-2.0).
2. Mascot name and voice guidelines per language.
3. Curated famous-route list source (manual seed vs prominence heuristic).
4. Claude.ai marketplace install path verification.
5. Static map tile source and licence for embedded report images.
6. Hosted WhatsApp bridge operator and data policy (Phase 3).
7. Domain, package names, trademark check for "Bergbot".

## 26. Pre-build due diligence
1. Source + licence + update-frequency matrix per adapter.
2. Ten real hikes audited manually against the same sources (benchmark seed).
3. Five hard cases (closure, fire ban, wind, quiet zone, ambiguous lift status).
4. Prototype: sentence → audit JSON → HTML → Telegram → GPX → swisstopo import, tested on iPhone and Android.
5. Telegram local poller proof of concept; WhatsApp Cloud API feasibility and cost.
6. Claude Code and Claude.ai plugin install test from a fresh account.
7. Safety wording review EN/FR/DE/IT by native speakers with mountain background.
8. Register tests: 20 messages that must be serious, 20 that may be playful.
9. Naming/trademark/domain search.
10. Waitlist page live before code is public.
