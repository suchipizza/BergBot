"""FR-R5 / SR: no locale string, template or rendered output may call a route or day 'safe'."""

from __future__ import annotations

from pathlib import Path

from tests.safety.forbidden import find_forbidden, scan_locale_files

ROOT = Path(__file__).resolve().parents[2]


def test_locale_files_clean() -> None:
    assert scan_locale_files() == []


def test_templates_clean() -> None:
    tpl_dir = ROOT / "src" / "bergbot" / "ui" / "report" / "templates"
    for path in tpl_dir.rglob("*.html*"):
        hits = find_forbidden(path.read_text(encoding="utf-8"))
        assert not hits, f"{path}: {hits}"


def test_plugin_skills_do_not_promise_safety() -> None:
    """Skill prompts instruct the LLM; they must not model the forbidden verdict phrases as output."""
    for path in (ROOT / "plugins").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        # Skills are allowed to *mention* forbidden words when telling the model never to use them.
        for line in text.splitlines():
            if "never" in line.lower() or "forbidden" in line.lower() or "do not" in line.lower():
                continue
            hits = find_forbidden(line, ["en"])
            assert not hits, f"{path}: {line!r} -> {hits}"


def test_scanner_catches_examples() -> None:
    assert find_forbidden("This route is safe today", ["en"])
    assert find_forbidden("Le sentier est sans danger", ["fr"])
    assert find_forbidden("Die Route ist sicher.", ["de"])
    assert find_forbidden("Il sentiero è sicuro", ["it"])
    # word-boundary: compound German words are not verdicts
    assert not find_forbidden("Trittsicherheit nötig", ["de"])
    assert not find_forbidden("Unsafe conditions", ["en"])
