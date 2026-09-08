"""FR-L1: four locale packs of equal completeness — CI-enforced."""

from __future__ import annotations

import pytest

from bergbot.i18n import LANGS, PACK_FILES, completeness, load
from bergbot.paths import locales_dir


def test_all_pack_files_exist() -> None:
    for lang in LANGS:
        for name in PACK_FILES:
            assert (locales_dir() / lang / f"{name}.yaml").exists(), f"{lang}/{name}.yaml missing"


def test_key_sets_identical() -> None:
    missing = completeness()
    problems = {lang: sorted(keys) for lang, keys in missing.items() if keys}
    assert not problems, f"locale packs differ: {problems}"


@pytest.mark.parametrize("lang", LANGS)
def test_placeholders_match_english(lang: str) -> None:
    """Every string must use the same {placeholders} as its English counterpart."""
    import re

    en = dict(load("en").strings())
    other = dict(load(lang).strings())
    ph = re.compile(r"\{(\w+)")
    for key, en_val in en.items():
        if key not in other:
            continue
        assert set(ph.findall(en_val)) == set(ph.findall(other[key])), f"{lang}:{key} placeholders differ"


@pytest.mark.parametrize("lang", LANGS)
def test_no_empty_strings(lang: str) -> None:
    for key, val in load(lang).strings():
        assert val.strip(), f"{lang}:{key} is empty"
