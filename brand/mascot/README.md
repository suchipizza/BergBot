# Bergbot mascot

The mascot is a small robot in a red Swiss beanie who dresses for the activity. The artwork is © 2026 the
Bergbot founder and is **not** covered by the MIT licence of the code. Contributors may not alter it; you may
use the `dist/` assets unchanged to reference Bergbot (README badges, blog posts, install guides).

## Files

| Path | What |
|---|---|
| `src/<variant>.png` | Source art, ≥ 1024 px on the long side (white or transparent background) |
| `dist/<variant>.webp` | 256 px, ≤ 40 KB, transparent — used in the HTML report |
| `dist/<variant>.datauri.txt` | `data:image/webp;base64,…` snippet for inlining |
| `dist/<variant>-512.png` | 512 px PNG for README / website hero |
| `dist/avatar.png` | 512 px square for the Telegram bot avatar (from `default`) |
| `manifest.json` | activity → variant mapping and placement rules |

Variants (source names): `default`, `hike`, `alpine-hike`, `ski-tour`, `trail-run`; optional extras
`snowshoe`, `mtb`, `climb`, `bivouac`, `dog`. Missing variants fall back to `default`; missing art falls back
to a neutral placeholder square carrying the variant name, so the build never depends on the artwork.

Run `uv run bergbot brand build` after dropping new art into `src/`. It removes a near-white background
automatically (source renders are on white), resizes and re-encodes.

## Placement rules (enforced in templates and tests)

- Never inside or adjacent to the warnings block (`#before-you-go`).
- Never in a `serious`-register message.
- Never on the Safety & sources page of the website.
- Report header: activity variant. Report footer: `default`. Telegram avatar: `default`.
