"""Locale packs: loading, lookup, completeness.

Boundary: the only module that reads `locales/`. All user-facing strings come from here; code holds keys.
Keys are dotted: "<file>.<path.to.key>", e.g. "safety.fixed_line", "warnings.trail_closure.title".
Four packs (en, fr, de, it) must have identical key sets — enforced by tests/i18n and `completeness()`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

from bergbot.paths import locales_dir

Lang = Literal["en", "fr", "de", "it"]
LANGS: tuple[Lang, ...] = ("en", "fr", "de", "it")
PACK_FILES: tuple[str, ...] = ("ui", "warnings", "safety", "suggestions", "playful", "report")


class MissingKey(KeyError):
    pass


def _flatten(d: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, Mapping):
            yield from _flatten(v, key)
        else:
            yield key, v


@dataclass(frozen=True)
class Locale:
    lang: Lang
    data: Mapping[str, Any] = field(repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in key.split("."):
            if isinstance(node, Mapping) and part in node:
                node = node[part]
            else:
                return default
        return node

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate `key`, formatting with kwargs. Raises MissingKey when absent (never silently falls back)."""
        value = self.get(key, None)
        if value is None:
            raise MissingKey(f"{self.lang}: {key}")
        if not isinstance(value, str):
            raise MissingKey(f"{self.lang}: {key} is not a string")
        return value.format(**kwargs) if kwargs else value

    def list(self, key: str) -> list[Any]:
        value = self.get(key, None)
        if value is None:
            raise MissingKey(f"{self.lang}: {key}")
        if not isinstance(value, list):
            raise MissingKey(f"{self.lang}: {key} is not a list")
        return value

    def keys(self) -> set[str]:
        return {k for k, _ in _flatten(self.data)}

    def strings(self) -> Iterator[tuple[str, str]]:
        """Every string leaf (lists expanded) — used by the forbidden-vocabulary scan."""
        for k, v in _flatten(self.data):
            if isinstance(v, str):
                yield k, v
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        yield f"{k}[{i}]", item
                    elif isinstance(item, Mapping):
                        for kk, vv in _flatten(item, f"{k}[{i}]"):
                            if isinstance(vv, str):
                                yield kk, vv


def _load_pack(lang: str, root: Path) -> dict[str, Any]:
    pack: dict[str, Any] = {}
    for name in PACK_FILES:
        path = root / lang / f"{name}.yaml"
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                pack[name] = yaml.safe_load(fh) or {}
        else:
            pack[name] = {}
    return pack


@lru_cache(maxsize=8)
def load(lang: str) -> Locale:
    if lang not in LANGS:
        raise ValueError(f"unsupported language {lang!r}; expected one of {LANGS}")
    return Locale(lang=lang, data=_load_pack(lang, locales_dir()))


def normalise_lang(value: str | None, default: Lang = "en") -> Lang:
    """Map 'de-CH', 'fr_FR', 'IT' → pack code. Unknown → default."""
    if not value:
        return default
    code = value.strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGS else default


def completeness() -> dict[str, set[str]]:
    """Return keys missing per language relative to the union of all packs. Empty sets == complete."""
    packs = {lang: load(lang).keys() for lang in LANGS}
    union: set[str] = set().union(*packs.values())
    return {lang: union - keys for lang, keys in packs.items()}
