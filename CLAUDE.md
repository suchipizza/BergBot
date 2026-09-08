# Bergbot — instructions for Claude Code working in this repo

You are building Bergbot, an open-source, local-first mountain-planning agent for Switzerland (hiking first),
in EN/FR/DE/IT. Read docs/BERGBOT_PRD.md and docs/BERGBOT_WORK_ORDER.md before any task. Work milestone by milestone.

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
