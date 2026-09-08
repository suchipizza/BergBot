# Contributing to Bergbot

Thanks for helping people check the mountains before they go. Three kinds of contribution are especially welcome:

## Good first canton
Cantonal closure, fire-ban or hut-status feeds that are machine-readable but not yet wired. Steps: add a row in
`docs/data-licences.md` (source, licence, redistribution yes/no, attribution, update frequency — if unclear, fetch
at runtime), implement an adapter in `src/bergbot/sources/ch/<name>/` following `sources/base.py` (`fetch`,
`freshness`, `licence`, `health`), record fixtures with `scripts/record_fixtures.py`, add a contract test in
`tests/source_contracts/`, a README in the adapter folder, and register it in `sources/registry.py`.

## Good first source
A new layer for the audit (e.g. webcams, avalanche terrain, hut opening feeds). Same steps as above, plus the
core hook: where the finding becomes a `Warning` (`core/conditions/zones.py` or `weather.py`) with an evidence
class and a locale entry in all four `locales/*/warnings.yaml`.

## Good first language string
Playful strings are written natively per language, never machine-translated. Safety strings (`safety.yaml`) are
locked: propose changes in a PR with the reasoning; a native speaker with mountain background reviews them.

## Rules (they are tested)
- Never a verdict: no "safe" or equivalents in any language, anywhere (`tests/safety`).
- Warnings first; the fixed line closes every warnings block.
- Geometry, distances, intersections, timetables and register are computed in `core/` — the LLM explains.
- Unverified stays unverified. No off-network route synthesis.
- Four locale packs with identical keys (`tests/i18n`). No hardcoded user-facing strings.
- Every adapter: fixtures, contract test, README, licence row. Every milestone: CHANGELOG entry.

## Workflow
`uv sync --all-extras --dev` · `uv run pytest` · `uv run ruff check && uv run ruff format` · `uv run mypy src/bergbot`.
Commit style: `feat(source/ch/xyz): …`, `feat(i18n/fr): …`, `fix(report): …`, `docs(install): …`.
Record decisions in `docs/decisions/NNN-title.md`.

The mascot artwork may not be altered (see `brand/mascot/README.md`).
