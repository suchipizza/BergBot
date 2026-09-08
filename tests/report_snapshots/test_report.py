"""M4 acceptance: snapshot per locale, size guard, forbidden vocabulary on rendered HTML, mascot rules (FR-H9)."""

from __future__ import annotations

import html as html_mod
import json
import re
from pathlib import Path

import pytest

from bergbot.core.domain import Audit, Severity
from bergbot.core.reporting.render import render_report
from bergbot.i18n import LANGS
from tests.safety.forbidden import find_forbidden

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "workflows"


def _audit(name: str = "waldstaetterweg-brunnen-vitznau") -> Audit:
    doc = json.loads((FIX / f"{name}.audit.json").read_text(encoding="utf-8"))
    return Audit.model_validate(doc)


def _stable(html: str) -> str:
    """Strip volatile bits (generation timestamps, data URIs) so snapshots only change on real template changes."""
    html = re.sub(r"data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+", "data:IMAGE", html)
    html = re.sub(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}", "TS", html)
    return html


@pytest.mark.parametrize("lang", LANGS)
def test_snapshot(lang: str, snapshot: object) -> None:
    html, warn = render_report(_audit(), lang=lang, with_map=False)
    assert warn is None
    snapshot.snapshot_dir = str(Path(__file__).parent / "snapshots")  # type: ignore[attr-defined]
    snapshot.assert_match(_stable(html), f"waldstaetterweg-{lang}.html")  # type: ignore[attr-defined]


@pytest.mark.parametrize("lang", LANGS)
def test_no_forbidden_vocabulary_and_self_contained(lang: str) -> None:
    html, _ = render_report(_audit(), lang=lang, with_map=False)
    text = re.sub(r"<[^>]+>", " ", html)
    assert find_forbidden(text, [lang]) == []
    # no external requests: every src/href that is not http link text must be data: or anchor
    for m in re.finditer(r'(?:src|href)="([^"]+)"', html):
        v = m.group(1)
        assert v.startswith(("data:", "https://", "http://", "#")), v
    assert "<script" not in html.lower()
    assert "@import" not in html and "url(" not in html
    assert len(html.encode("utf-8")) < 2_000_000


def test_sections_in_required_order() -> None:
    html, _ = render_report(_audit(), lang="en", with_map=False)
    ids = ["before-you-go", "route", "conditions", "terrain", "logistics", "around", "evidence"]
    positions = [html.index(f'id="{i}"') for i in ids]
    assert positions == sorted(positions)
    assert html.index("<footer") > positions[-1]


def test_fixed_line_closes_warnings_block() -> None:
    for lang in LANGS:
        html, _ = render_report(_audit(), lang=lang, with_map=False)
        block = html[html.index('id="before-you-go"') : html.index('id="route"')]
        from bergbot.i18n import load

        assert load(lang).t("safety.fixed_line") in html_mod.unescape(block)


def test_mascot_never_in_warnings_and_absent_from_header_when_critical() -> None:
    a = _audit()
    assert a.max_severity is Severity.critical
    html, _ = render_report(a, lang="en", with_map=False)
    block = html[html.index('id="before-you-go"') : html.index('id="route"')]
    assert "mascot" not in block
    assert 'id="header-mascot"' not in html  # critical → footer only
    assert html.count('class="mascot"') == 1  # footer
    # playful audit (no warnings) → header mascot present, still never in the warnings block
    a2 = _audit()
    a2.warnings = []
    html2, _ = render_report(a2, lang="fr", with_map=False)
    assert 'id="header-mascot"' in html2
    block2 = html2[html2.index('id="before-you-go"') : html2.index('id="route"')]
    assert "mascot" not in block2


def test_evidence_classes_displayed() -> None:
    html, _ = render_report(_audit(), lang="it", with_map=False)
    for c in "ABCDE":
        assert f'class="badge {c}"' in html


def test_size_guard_raises_over_2mb(monkeypatch: pytest.MonkeyPatch) -> None:
    from bergbot.core.reporting import render as r

    monkeypatch.setattr(r, "SIZE_FAIL", 10)
    with pytest.raises(r.ReportTooLarge):
        render_report(_audit(), lang="en", with_map=False)
