from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

# Tests never touch the user's real ~/.bergbot; they never hit the network unless marked `online`.
os.environ.setdefault("BERGBOT_HOME", str(ROOT / ".pytest_cache" / "bergbot-home"))
os.environ.setdefault("BERGBOT_OFFLINE", "1")


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "online: needs network access (skipped in CI)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("BERGBOT_ONLINE_TESTS"):
        return
    skip = pytest.mark.skip(reason="set BERGBOT_ONLINE_TESTS=1 to run online tests")
    for item in items:
        if "online" in item.keywords:
            item.add_marker(skip)
