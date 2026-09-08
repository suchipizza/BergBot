# Benchmark

`uv run bergbot benchmark` audits the 10 routes in `routes/` and checks each result against `reference.yaml`:
distance ±3 %, ascent ±10 %, static-layer warning types present (quiet zones, protected areas, shooting zones,
guardian dogs, exposure), no amenity open/closed without verified evidence, the fixed line in the message,
≤ 12 lines, network membership. `--offline` (default in CI) replays `fixtures/*.json.gz`; `--online` hits the
live sources. `scripts/build_benchmark_reference.py` re-seeds the reference and fixtures.

Live findings (closures, weather, fire danger) are reported in `results.md` but not asserted — they change daily.

**FOUNDER INPUT:** for 3–5 routes you know well, add under `founder_notes` what you expect Bergbot to flag
(a closure you know of, a hut that is closed on Mondays, a ridge that is windy in the afternoon…). Turn each
note into an `expect.warning_types` entry or a new check when it is verifiable from a source.

Routes: Waldstätterweg Brunnen–Vitznau · Schwyzer Höhenweg Küssnacht–Rigi · Rigi-Panoramaweg · Vier-Seen-Wanderung ·
5-Seen-Wanderung Pizol · Aletsch Panoramaweg · Sentier du Creux du Van · Clariden-Höhenweg · Walliser Sonnenweg
Leukerbad–Gampel · Via Alpina Griesalp–Kandersteg.
