from __future__ import annotations

from pathlib import Path

import pytest

from bergbot.sources.http import FixtureFetcher

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="session")
def wf_fetcher() -> FixtureFetcher:
    f = FixtureFetcher.from_files(
        *sorted((FIX / "workflows").glob("*.json.gz")), *sorted((FIX / "sources").glob("*.json"))
    )
    f.strict = True
    return f
