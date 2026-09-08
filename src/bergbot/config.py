"""Project-level configuration: public URLs used in the report footer, README and website (UTM-tagged)."""

from __future__ import annotations

import tomllib
from functools import lru_cache

from bergbot.paths import repo_root

DEFAULTS = {
    "github_url": "https://github.com/suchipizza/BergBot",
    "website_url": "https://suchipizza.github.io/BergBot",
    "waitlist_url": "https://tally.so/r/bergbot-waitlist",
}


@lru_cache(maxsize=1)
def settings() -> dict[str, str]:
    root = repo_root()
    if root is not None:
        try:
            data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
            cfg = data.get("tool", {}).get("bergbot", {})
            return {**DEFAULTS, **{k: str(v) for k, v in cfg.items()}}
        except (OSError, ValueError):
            pass
    return dict(DEFAULTS)


def utm(url: str, source: str, medium: str = "report") -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source={source}&utm_medium={medium}&utm_campaign=bergbot"
