"""Shared forbidden-vocabulary scanner (FR-R5). Imported by tests in several folders."""

from __future__ import annotations

import re
from collections.abc import Iterable

from bergbot.i18n import LANGS, load

# Locale-file keys that are allowed to contain the forbidden words — the forbidden lists themselves.
_ALLOWED_KEY_PREFIXES = ("safety.forbidden",)


def forbidden_patterns(lang: str) -> list[re.Pattern[str]]:
    words = load(lang).list("safety.forbidden")
    pats = []
    for w in words:
        # strip qualifiers such as "sicher (als Urteil)"
        core = re.sub(r"\s*\(.*?\)\s*", "", w).strip()
        if not core:
            continue
        pats.append(re.compile(rf"(?<!\w){re.escape(core)}(?!\w)", re.IGNORECASE))
    return pats


def find_forbidden(text: str, langs: Iterable[str] = LANGS) -> list[str]:
    hits: list[str] = []
    for lang in langs:
        for pat in forbidden_patterns(lang):
            if pat.search(text):
                hits.append(f"{lang}:{pat.pattern}")
    return hits


def scan_locale_files() -> list[str]:
    problems: list[str] = []
    for lang in LANGS:
        for key, value in load(lang).strings():
            if key.startswith(_ALLOWED_KEY_PREFIXES):
                continue
            for hit in find_forbidden(value, [lang]):
                problems.append(f"{lang}:{key} contains {hit}: {value!r}")
    return problems
