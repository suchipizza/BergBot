"""Locate data directories (locales, brand assets, seed data) in source checkouts and installed wheels.

Boundary: pure filesystem lookup; no I/O beyond existence checks. Everything that needs bundled data
goes through this module so packaging can change without touching callers.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def repo_root() -> Path | None:
    """Return the repository root when running from a source checkout, else None."""
    for parent in [_PKG_DIR, *_PKG_DIR.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "locales").is_dir():
            return parent
    return None


def data_root() -> Path:
    """Root that contains `locales/`, `brand/`, `data/` — repo root or the packaged `_data` folder."""
    override = os.environ.get("BERGBOT_DATA_ROOT")
    if override:
        return Path(override)
    root = repo_root()
    if root is not None:
        return root
    return _PKG_DIR / "_data"


def locales_dir() -> Path:
    return data_root() / "locales"


def brand_dir() -> Path:
    return data_root() / "brand" / "mascot"


def seed_data_dir() -> Path:
    return data_root() / "data"


def user_config_dir() -> Path:
    """Per-user config and cache directory (tokens, caches). Never inside the repo."""
    override = os.environ.get("BERGBOT_HOME")
    if override:
        return Path(override)
    return Path.home() / ".bergbot"


def cache_dir() -> Path:
    d = user_config_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d
