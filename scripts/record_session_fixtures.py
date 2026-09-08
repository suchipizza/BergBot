"""Record the source responses behind the three canonical prompts so the session e2e test runs offline.
Run: uv run python scripts/record_session_fixtures.py"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bergbot.agent.session import Session  # noqa: E402
from bergbot.sources.http import HttpFetcher  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "workflows" / "session.json"
GPX = ROOT / "tests" / "fixtures" / "gpx" / "rigi-stage.gpx"

PROMPTS = [
    ("Generate a hike on 2026-09-12 with less than 500 m up in canton Glarus", None),
    ("Can you find a hike near Brunnen on 2026-09-12?", None),
    ("1", None),
    ("send me the gpx", None),
    ("Check if this hike is good on 2026-09-12", GPX),
]


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    f = HttpFetcher(record_to=OUT)
    work = ROOT / ".pytest_cache" / "session-record"
    work.mkdir(parents=True, exist_ok=True)
    s = Session(workdir=work, fetcher=f, with_map=False)
    for text, att in PROMPTS:
        r = s.handle(text, attachment=att, progress=lambda m: print("  …", m))
        print("---", text)
        print(r.message.text)
    with gzip.open(OUT.with_suffix(".json.gz"), "wt", encoding="utf-8") as fh:
        fh.write(OUT.read_text(encoding="utf-8"))
    OUT.unlink()


if __name__ == "__main__":
    main()
