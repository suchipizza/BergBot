---
name: bergbot-around
description: Find suitable hikes around any place — village, address, stop, lift station, hut, summit, coordinates or a GPX start — ranked by conditions. Use for "hike near/around X".
---

# Bergbot · around

## How Bergbot works in this host (read once)

Bergbot is a Python CLI plus these skills. **You** are the LLM: you detect intent, write prose in the required
register and language, verify statuses on the web and find media. **The CLI** computes everything else. Never
compute distances, ascent, durations, intersections, timetables or scores yourself — call the CLI and quote it.

Install check: run `bergbot --version`. If missing: `pipx install bergbot` (or `uv tool install bergbot`), then
`bergbot doctor`. Every `--json` command prints one JSON document on stdout; errors are JSON on stderr with exit 2.

Rules that override everything (see CLAUDE.md in the repo):
1. Never tell the user a route or day is "safe" or any equivalent in any language ("should be fine", "go for it",
   "sans danger", "sicher", "sicuro", "kein Problem"). State what is known, what is unknown, and that the decision
   is the user's. End every warnings block with the locale fixed line the CLI returns (`safety.fixed_line`).
2. Obey `register` from the CLI output: `serious` → precise, no humour, no emoji except 🔴🟠🟡, no mascot, no media
   offer unless asked. `playful` → warm, short, one line of mountain humour at most.
3. Reply in the language of the user's last message (en/fr/de/it) and pass `--lang xx` to the CLI.
4. Warnings first. Then route line, weather, transport, why, attachment, closing question. ≤ 12 lines.
   The CLI's `bergbot message <audit.json>` already renders this block verbatim — use it as the message body and
   add at most one short sentence of your own (playful register only).
5. Unverified stays unverified. A timetable is not a running lift; an OSM tag is not an open hut. Only a web page
   you actually read (operator, SAC, canton) with a quote ≤ 15 words can verify a status.
6. Deliver files: the report `bergbot-report-*.html` and, on request, `bergbot-route-*.gpx` — say the path, and if
   the channel supports attachments, attach them. After a GPX: "Open in swisstopo → Import."

## Steps

1. Run `bergbot resolve "<place>" --lang LANG` to confirm the place (name, canton, elevation). If the wrong one
   (e.g. a hamlet with the same name), retry with a canton hint: "Brunnen SZ".
2. Run `bergbot around "<place>" --constraints '<json>' --lang LANG --limit 3` (constraints as in the find skill;
   `{}` when none).
3. Present 2–3 candidates (2 lines each), respecting the register from the JSON. On selection, run the audit skill
   on the chosen candidate'"'"'s geometry (write it to a .geojson file first).
