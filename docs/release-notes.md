# Bergbot v0.1.0 — Phase 1 launch

Open-source, local-first mountain-planning agent for Switzerland (hiking). One sentence in EN/FR/DE/IT or a GPX →
warnings-first answer in ≤ 12 lines, a self-contained mobile HTML report, a GPX for swisstopo.

- Surfaces: Claude Code plugin (marketplace), Telegram (your own bot, local), CLI (`bergbot chat`), bring-your-own channel.
- Workflows: find · around · audit · check · export · media · help · chat · emergency short-circuit.
- 14 Swiss source adapters (GeoAdmin/swisstopo, SwitzerlandMobility closures, MeteoSwiss ICON via Open-Meteo, BAFU zones and fire danger, guardian dogs, army firing zones, transport.opendata.ch, SLF presence, OSM), contract-tested with recorded fixtures.
- Deterministic core (geometry, terrain, routing on the official network, conditions, logistics, scoring, evidence A–E), rule-based register, forbidden-vocabulary and safety-regression gates, 10-route benchmark.
- Four locale packs of equal completeness; playful strings written natively.

Install: `pipx install "bergbot[all]"` · `/plugin marketplace add suchipizza/BergBot` · `/plugin install bergbot`.
