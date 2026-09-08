"""FR-M1–M3 and FR-R3/R5: message ≤ 12 lines, fixed order, register rules, no forbidden vocabulary, four locales."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bergbot.conversation.message import (
    render_audit_message,
    render_candidates_message,
    render_check_message,
    render_emergency,
    render_help,
)
from bergbot.conversation.register import decide
from bergbot.conversation.suggestions import suggest
from bergbot.core.domain import (
    Audit,
    CandidateSet,
    CheckResult,
    Intent,
    QuestionKind,
    Register,
    RouteCandidate,
    Severity,
)
from bergbot.i18n import LANGS, load
from tests.safety.forbidden import find_forbidden

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "workflows"


def _audit() -> Audit:
    return Audit.model_validate(
        json.loads((FIX / "waldstaetterweg-brunnen-vitznau.audit.json").read_text(encoding="utf-8"))
    )


@pytest.mark.parametrize("lang", LANGS)
def test_audit_message_shape(lang: str) -> None:
    a = _audit()
    reg = decide(a, Intent.audit, QuestionKind.none)
    assert reg.mode is Register.serious  # closure → serious
    m = render_audit_message(a, reg, lang=lang)
    L = load(lang)
    assert len(m.lines) <= 12
    # fixed order: warnings header first, fixed line closes the block, then route, weather, transport … closing question
    assert m.lines[0] == L.t("ui.message.warnings_header")
    idx_fixed = m.lines.index(L.t("safety.fixed_line"))
    assert "🔴" in m.lines[1]
    assert a.route.name in m.lines[idx_fixed + 1]
    assert m.lines[-2].startswith(L.t("ui.message.attachment_line", filename="").strip())
    assert m.lines[-1] == L.t("ui.message.closing_question")  # serious → no media offer
    # serious: no emoji other than severity markers
    for line in m.lines:
        for ch in line:
            if ord(ch) > 0x2600 and ch not in "🔴🟠🟡⚠↑↓→·–":
                raise AssertionError(f"emoji {ch!r} in serious message: {line}")
    assert find_forbidden(m.text, [lang]) == []
    assert m.attachments == ["bergbot-report.html"]


def test_playful_message_offers_media_when_famous() -> None:
    a = _audit()
    a.warnings = []
    reg = decide(a, Intent.audit, QuestionKind.none)
    assert reg.mode is Register.playful
    m = render_audit_message(a, reg, lang="en")
    assert m.lines[-1] == load("en").t("ui.message.closing_question_media")
    assert "📷" in m.buttons


def test_candidates_message() -> None:
    a = _audit()
    cs = CandidateSet(
        intent=Intent.around,
        constraints=a.model_dump(include={"date"})
        and __import__("bergbot.core.domain", fromlist=["Constraint"]).Constraint(date=a.date),
        place=a.route.start,
        candidates=[
            RouteCandidate(route=a.route, score=80.0, warnings=a.warnings, weather_summary="clear|12|20|15")
        ],
        lang="de",
        generated_at=a.generated_at,
    )
    reg = decide(None, Intent.around, QuestionKind.none)
    m = render_candidates_message(cs, reg)
    assert len(m.lines) <= 12 and "1." in m.lines[1] and m.buttons == ["1"]
    assert find_forbidden(m.text, ["de"]) == []


@pytest.mark.parametrize("lang", LANGS)
def test_emergency_short_circuit(lang: str) -> None:
    m = render_emergency(lang)
    assert "1414" in m.text and "112" in m.text and m.mode is Register.serious and len(m.lines) <= 6


@pytest.mark.parametrize("lang", LANGS)
def test_help_and_suggestions(lang: str) -> None:
    s = suggest(lang, region="ti", month=7)
    assert len(s) == 4 and any(x.kind is Intent.audit for x in s)
    assert all(not x.months or 7 in x.months for x in s)
    m = render_help(lang, [x.text for x in s])
    assert len(m.lines) <= 12 and m.mode is Register.playful


def test_check_message_unverified() -> None:
    from datetime import UTC, datetime

    cr = CheckResult(
        kind="lift", name="Gemmibahn", date="2026-09-13", generated_at=datetime.now(tz=UTC), lang="fr"
    )
    m = render_check_message(cr)
    assert load("fr").t("safety.terms.unverified") in m.lines[0] and m.lines[-1] == load("fr").t(
        "safety.fixed_line"
    )


def test_severity_markers_are_the_only_emoji_in_serious() -> None:
    a = _audit()
    assert a.max_severity is Severity.critical
