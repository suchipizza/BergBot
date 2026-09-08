"""Record every source response needed to audit the fixture GPX files offline.
Run: uv run python scripts/record_workflow_fixtures.py  (network)"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bergbot.core.workflows import run_audit  # noqa: E402
from bergbot.sources.http import HttpFetcher  # noqa: E402

GPX = ROOT / "tests" / "fixtures" / "gpx"
OUT = ROOT / "tests" / "fixtures" / "workflows"
DATE = "2026-09-12"

CASES = {
    "waldstaetterweg-brunnen-vitznau": {"origin": "Zürich HB"},
    "rigi-stage": {"origin": "Luzern"},
    "glarus-stage": {"origin": "Zürich HB"},
}


def main() -> None:
    for name, kw in CASES.items():
        path = OUT / f"{name}.json"
        if path.exists():
            path.unlink()
        f = HttpFetcher(record_to=path)
        audit = run_audit(
            GPX / f"{name}.gpx", date=DATE, start_time="09:00", lang="en", fetcher=f, origin=kw["origin"]
        )
        (OUT / f"{name}.audit.json").write_text(
            json.dumps(
                audit.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=1, default=str
            ),
            encoding="utf-8",
        )
        s = audit.route.stats
        print(
            f"{name}: {s.distance_km} km ↑{s.ascent_m} ↓{s.descent_m} {s.duration_min} min; warnings={[w.type.value for w in audit.warnings]}; unavailable={audit.summary.unverified}"
        )


if __name__ == "__main__":
    main()
