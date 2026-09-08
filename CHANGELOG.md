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
