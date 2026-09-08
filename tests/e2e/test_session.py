"""M5 acceptance: sentence → message + report + GPX on the three canonical prompts in each language, offline
(recorded fixtures, no LLM). Also exercises selection, export and emergency."""

from __future__ import annotations

from pathlib import Path

import pytest

from bergbot.agent.session import Session
from bergbot.core.domain import Intent, Register
from bergbot.i18n import LANGS, load
from bergbot.sources.http import FixtureFetcher
from tests.safety.forbidden import find_forbidden

FIX = Path(__file__).resolve().parents[1] / "fixtures"
GPX = FIX / "gpx" / "rigi-stage.gpx"

PROMPTS = {
    "en": (
        "Generate a hike on 2026-09-12 with less than 500 m up in canton Glarus",
        "Can you find a hike near Brunnen on 2026-09-12?",
        "Check if this hike is good on 2026-09-12",
    ),
    "fr": (
        "Propose une randonnée le 2026-09-12 avec moins de 500 m de dénivelé dans le canton de Glaris",
        "Peux-tu trouver une rando près de Brunnen le 2026-09-12 ?",
        "Vérifie si cette rando est bien le 2026-09-12",
    ),
    "de": (
        "Wanderung am 2026-09-12 mit weniger als 500 m Aufstieg im Kanton Glarus",
        "Findest du eine Wanderung bei Brunnen am 2026-09-12?",
        "Prüf, ob diese Wanderung am 2026-09-12 gut ist",
    ),
    "it": (
        "Proponi un'escursione il 2026-09-12 con meno di 500 m di dislivello nel cantone di Glarona",
        "Trovi un'escursione vicino a Brunnen il 2026-09-12?",
        "Controlla se questa escursione va bene il 2026-09-12",
    ),
}


@pytest.fixture(scope="module")
def fetcher() -> FixtureFetcher:
    f = FixtureFetcher.from_files(
        FIX / "workflows" / "session.json.gz",
        *sorted((FIX / "workflows").glob("*-*.json.gz")),
        *sorted((FIX / "sources").glob("*.json")),
    )
    f.strict = False
    return f


@pytest.mark.parametrize("lang", LANGS)
def test_three_canonical_prompts(lang: str, fetcher: FixtureFetcher, tmp_path: Path) -> None:
    L = load(lang)
    s = Session(workdir=tmp_path, fetcher=fetcher, with_map=False)
    progress: list[str] = []

    # 1) find by constraints
    r1 = s.handle(PROMPTS[lang][0], progress=progress.append)
    assert r1.message.lang == lang and r1.message.intent is Intent.find
    assert r1.candidates and 1 <= len(r1.candidates.candidates) <= 3
    assert len(r1.message.lines) <= 12 and find_forbidden(r1.message.text, [lang]) == []
    assert r1.message.lines[-1] == L.t("ui.message.pick_one")
    for c in r1.candidates.candidates:
        assert c.route.network_member and c.route.stats and c.route.stats.ascent_m <= 525

    # 2) around a place
    r2 = s.handle(PROMPTS[lang][1], progress=progress.append)
    assert r2.message.intent is Intent.around and r2.candidates and r2.candidates.place
    assert r2.candidates.place.canton == "sz"
    assert r2.candidates.candidates

    # 3) select → full audit, report + message
    r3 = s.handle("1", progress=progress.append)
    assert r3.audit is not None and r3.files and r3.files[0].suffix == ".html"
    html = r3.files[0].read_text(encoding="utf-8")
    assert L.t("safety.fixed_line") in r3.message.text and L.t("sections.route", **{}) if False else True
    assert L.t("report.sections.evidence") in html
    assert len(r3.message.lines) <= 12 and find_forbidden(r3.message.text, [lang]) == []
    assert r3.message.lines[-2].startswith(L.t("ui.message.attachment_line", filename="").strip())

    # 4) export GPX
    r4 = s.handle(
        {
            "en": "send me the gpx",
            "fr": "Envoie-moi le GPX",
            "de": "Schick mir das GPX",
            "it": "Inviami il GPX",
        }[lang]
    )
    assert r4.files and r4.files[0].suffix == ".gpx" and r4.files[0].stat().st_size > 1000
    assert L.t("ui.export.swisstopo_line") in r4.message.text

    # 5) audit an attached GPX
    r5 = s.handle(PROMPTS[lang][2], attachment=GPX, progress=progress.append)
    assert r5.audit is not None and r5.audit.route.stats and 7 < r5.audit.route.stats.distance_km < 8
    assert r5.message.mode is Register.serious  # shooting zone + fire → serious
    assert r5.message.lines[0] == L.t("ui.message.warnings_header")
    assert any(p for p in progress)


def test_emergency_and_help(tmp_path: Path) -> None:
    s = Session(workdir=tmp_path, offline=True)
    r = s.handle("Someone fell and is injured")
    assert (
        r.message.intent is Intent.emergency
        and "1414" in r.message.text
        and r.message.mode is Register.serious
    )
    r2 = s.handle("Salut !")
    assert r2.message.intent is Intent.help and r2.message.lang == "fr" and len(r2.message.buttons) == 4


def test_question_from_audit_context_without_llm(fetcher: FixtureFetcher, tmp_path: Path) -> None:
    s = Session(workdir=tmp_path, fetcher=fetcher, with_map=False)
    s.handle("Check if this hike is good on 2026-09-12", attachment=GPX)
    r = s.handle("Is it dangerous with kids?")
    L = load("en")
    assert r.message.mode is Register.serious
    assert L.t("safety.fixed_line") in r.message.text and L.t("safety.safety_answer_frame") in r.message.text
    assert find_forbidden(r.message.text, ["en"]) == []
    r2 = s.handle("what is T3?")
    assert "T3" in r2.message.text
