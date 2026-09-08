"""Seed docs/benchmark/reference.yaml from a live run (stats + static-layer warning types) and record fixtures.
Founder reference findings are added by hand afterwards (see FOUNDER INPUT rows). Run once, then review."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bergbot.benchmark import BENCH, DATE, run_benchmark, write_results  # noqa: E402
from bergbot.core.workflows import run_audit  # noqa: E402

STATIC = {"wildlife_quiet_zone", "protected_area", "shooting_zone", "guardian_dogs", "exposed_terrain"}
ORIGINS = {
    "waldstaetterweg-brunnen-vitznau": "Zürich HB",
    "rigi-stage": "Luzern",
    "rigi-panoramaweg": "Luzern",
    "vier-seen-wanderung": "Luzern",
    "pizol-5-seen": "Zürich HB",
    "aletsch-panoramaweg": "Bern",
    "creux-du-van": "Neuchâtel",
    "clariden-hoehenweg": "Zürich HB",
    "walliser-sonnenweg-leukerbad": "Sion",
    "via-alpina-griesalp-kandersteg": "Bern",
}


def main() -> None:
    routes = []
    for gpx in sorted((BENCH / "routes").glob("*.gpx")):
        a = run_audit(gpx, date=DATE, lang="en", origin=ORIGINS.get(gpx.stem))
        s = a.route.stats
        assert s
        types = sorted({w.type.value for w in a.warnings} & STATIC)
        routes.append(
            {
                "slug": gpx.stem,
                "name": a.route.name,
                "origin": ORIGINS.get(gpx.stem),
                "date": DATE,
                "expect": {"distance_km": s.distance_km, "ascent_m": s.ascent_m, "warning_types": types},
                "founder_notes": "FOUNDER INPUT — what would you expect Bergbot to flag on this route?",
            }
        )
        print(gpx.stem, s.distance_km, s.ascent_m, types)
    (BENCH / "reference.yaml").write_text(
        "# Benchmark reference. Stats from swissALTI3D on the recording date; warning_types = static layers that\n"
        "# must always be found. Live findings (closures, weather, fire) are reported, not asserted.\n"
        + yaml.safe_dump({"routes": routes}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (BENCH / "fixtures").mkdir(exist_ok=True)
    result = run_benchmark(offline=False, record=True)
    print(write_results(result))


if __name__ == "__main__":
    main()
