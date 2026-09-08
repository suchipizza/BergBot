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
