"""FR-C4: 4 localised, seasonal, region-aware suggestions."""

from __future__ import annotations

from datetime import date

from bergbot.core.domain import Intent, Suggestion
from bergbot.i18n import load, normalise_lang


def suggest(
    lang: str = "en", region: str | None = None, month: int | None = None, n: int = 4
) -> list[Suggestion]:
    L = load(normalise_lang(lang))
    month = month or date.today().month
    items = [
        Suggestion(
            text=i["text"],
            kind=Intent(i["kind"]),
            months=list(i.get("months") or []),
            regions=list(i.get("regions") or []),
        )
        for i in L.list("suggestions.items")
    ]
    always = [Suggestion(text=i["text"], kind=Intent(i["kind"])) for i in L.list("suggestions.always")]

    def score(s: Suggestion) -> tuple[int, int]:
        season = 0 if not s.months or month in s.months else 1
        reg = 0 if (region and region in s.regions) else 1 if not s.regions else 2
        return (season, reg)

    ranked = sorted(items, key=score)
    out: list[Suggestion] = []
    kinds_seen: set[Intent] = set()
    for s in ranked:
        if score(s)[0] == 1:
            continue
        if s.kind in kinds_seen and len(out) < n - 1:
            continue
        out.append(s)
        kinds_seen.add(s.kind)
        if len(out) == n - 1:
            break
    for s in ranked:
        if len(out) >= n - 1:
            break
        if s not in out:
            out.append(s)
    out.extend(always[: n - len(out)])
    return out[:n]


def intro(lang: str) -> str:
    return load(normalise_lang(lang)).t("suggestions.intro")
