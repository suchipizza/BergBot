"""FR-W6: famous-route detection and the web query spec for media links (links only, never re-hosted)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import yaml

from bergbot.core.domain import Audit, Route
from bergbot.paths import seed_data_dir
from bergbot.sources.shared.web import verification_spec


@lru_cache(maxsize=1)
def famous_routes() -> list[dict[str, Any]]:
    path = seed_data_dir() / "famous_routes.yaml"
    if not path.exists():
        return []
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(doc.get("routes", []))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def famous_match(route: Route) -> dict[str, Any] | None:
    name = _norm(route.name)
    for r in famous_routes():
        for cand in [r["name"], *r.get("aliases", [])]:
            if _norm(cand) and _norm(cand) in name:
                return r
    return None


def is_famous(route: Route) -> tuple[bool, str | None]:
    """Curated list match or prominence heuristic (SwitzerlandMobility national/regional route)."""
    m = famous_match(route)
    if m:
        return True, f"curated: {m['name']}"
    if route.identity.famous:
        return True, route.identity.famous_reason
    return False, None


def mark_famous(audit: Audit) -> Audit:
    famous, reason = is_famous(audit.route)
    audit.route.identity.famous = famous
    audit.route.identity.famous_reason = reason
    return audit


def media_query_spec(route: Route, lang: str = "en") -> dict[str, Any]:
    m = famous_match(route)
    spec = verification_spec("media", subject=route.name, name=route.name, date="")
    spec["official_url"] = m.get("official_url") if m else None
    spec["want"] = ["official", "gallery", "trip_report", "video"]
    spec["max_links"] = 5
    spec["lang"] = lang
    spec["rules"] = spec["rules"] + [
        "Return 3–5 links with a one-line description and a date; mark each as third-party.",
        "Links only — never copy or re-host images.",
        "These links are not part of the safety audit; say so.",
    ]
    return spec
