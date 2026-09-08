"""Registry of all source adapters (used by `bergbot doctor` and workflows)."""

from __future__ import annotations

from bergbot.sources.base import SourceAdapter


def all_adapters() -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    return adapters
