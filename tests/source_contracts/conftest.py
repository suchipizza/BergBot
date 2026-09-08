from __future__ import annotations

from pathlib import Path

import pytest

from bergbot.sources.http import FixtureFetcher

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "sources"


@pytest.fixture(scope="session")
def fetcher() -> FixtureFetcher:
    f = FixtureFetcher.from_files(*sorted(FIX.glob("*.json")))
    f.strict = False
    return f
