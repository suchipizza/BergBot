"""M5 acceptance: 40 intent fixtures (10 per language) ≥ 95 % correct; constraint extraction spot checks."""

from __future__ import annotations

from datetime import date

import pytest

from bergbot.conversation.intent import detect, detect_language
from bergbot.core.domain import Intent

TODAY = date(2026, 9, 9)  # Wednesday

FIXTURES: list[tuple[str, str, str, dict]] = [  # type: ignore[type-arg]
    # ---- EN ----
    (
        "Generate a hike for tomorrow with less than 500 m up in canton Glarus",
        "en",
        "find",
        {"region": "gl", "max_ascent_m": 500.0, "date": "2026-09-10"},
    ),
    ("Can you find a hike near Brunnen?", "en", "around", {"place": "Brunnen"}),
    ("Is the Gemmi gondola running Sunday?", "en", "check", {"date": "2026-09-13"}),
    (
        "Easy hike tomorrow, under 2 h from Zürich by train",
        "en",
        "find",
        {"origin": "Zürich", "max_travel_min": 120, "max_grade": "T2"},
    ),
    ("Something with a hut lunch near Engelberg", "en", "around", {"place": "Engelberg", "hut": True}),
    ("send me the gpx", "en", "export", {}),
    ("photos of this route", "en", "media", {}),
    ("someone fell and is injured", "en", "emergency", {}),
    ("what is T3?", "en", "chat", {}),
    ("Hike with my dog in Graubünden, no guardian-dog zones", "en", "find", {"region": "gr", "dog": True}),
    # ---- FR ----
    (
        "Randonnée facile demain, à moins de 2 h de Lausanne en train",
        "fr",
        "find",
        {"origin": "Lausanne", "max_travel_min": 120, "date": "2026-09-10"},
    ),
    (
        "Une rando près de Brunnen avec moins de 500 m de dénivelé",
        "fr",
        "around",
        {"place": "Brunnen", "max_ascent_m": 500.0},
    ),
    ("Le téléphérique de la Gemmi fonctionne-t-il dimanche ?", "fr", "check", {}),
    ("Y a-t-il une interdiction de feu au Tessin en ce moment ?", "fr", "check", {"region": "ti"}),
    (
        "Rando dans le canton de Fribourg demain, max 600 m de montée, retour en train",
        "fr",
        "find",
        {"region": "fr", "max_ascent_m": 600.0, "transport_required": True},
    ),
    ("Envoie-moi le GPX", "fr", "export", {}),
    ("Quelqu'un est tombé, il est blessé", "fr", "emergency", {}),
    ("plus court", "fr", "modify", {}),
    ("C'est dangereux avec des enfants ?", "fr", "chat", {}),
    ("Quelque chose près de Locarno avec un lac à l'arrivée", "fr", "around", {"place": "Locarno"}),
    # ---- DE ----
    (
        "Wanderung im Kanton Glarus morgen, max. 600 m rauf, mit dem Zug zurück",
        "de",
        "find",
        {"region": "gl", "max_ascent_m": 600.0, "transport_required": True},
    ),
    ("Etwas mit Hüttenzmittag bei Engelberg", "de", "around", {"place": "Engelberg", "hut": True}),
    ("Fährt die Gemmibahn am Sonntag?", "de", "check", {"date": "2026-09-13"}),
    ("Gilt im Tessin gerade ein Feuerverbot?", "de", "check", {"region": "ti"}),
    (
        "Leichte Wanderung morgen, unter 2 h ab Zürich mit dem Zug",
        "de",
        "find",
        {"origin": "Zürich", "max_travel_min": 120},
    ),
    ("Schick mir das GPX", "de", "export", {}),
    ("Jemand ist gestürzt und verletzt", "de", "emergency", {}),
    ("kürzer", "de", "modify", {}),
    ("Ist das gefährlich für ein Kind?", "de", "chat", {}),
    ("Wandern mit Hund in Graubünden", "de", "find", {"region": "gr", "dog": True}),
    # ---- IT ----
    (
        "Escursione facile domani, a meno di 2 h da Lugano in treno",
        "it",
        "find",
        {"origin": "Lugano", "max_travel_min": 120, "date": "2026-09-10"},
    ),
    (
        "Un'escursione vicino a Brunnen con meno di 500 m di dislivello",
        "it",
        "around",
        {"place": "Brunnen", "max_ascent_m": 500.0},
    ),
    ("La funivia della Gemmi funziona domenica?", "it", "check", {"date": "2026-09-13"}),
    ("C'è un divieto di fuochi in Ticino in questo momento?", "it", "check", {"region": "ti"}),
    (
        "Escursione in Ticino domani, max 600 m di salita, ritorno in treno",
        "it",
        "find",
        {"region": "ti", "max_ascent_m": 600.0},
    ),
    ("Inviami il GPX", "it", "export", {}),
    ("Qualcuno è caduto ed è ferito", "it", "emergency", {}),
    ("più corta", "it", "modify", {}),
    ("È pericoloso con i bambini?", "it", "chat", {}),
    ("Qualcosa vicino a Locarno con un lago all'arrivo", "it", "around", {"place": "Locarno"}),
]


def test_fixture_count() -> None:
    assert len(FIXTURES) == 40
    for lang in ("en", "fr", "de", "it"):
        assert sum(1 for f in FIXTURES if f[1] == lang) == 10


def test_intent_accuracy_at_least_95_percent() -> None:
    wrong = []
    for text, lang, intent, _ in FIXTURES:
        d = detect(text, today=TODAY)
        if d.intent.value != intent or d.lang != lang:
            wrong.append((text, d.intent.value, d.lang, intent, lang))
    rate = 1 - len(wrong) / len(FIXTURES)
    assert rate >= 0.95, wrong


@pytest.mark.parametrize(("text", "lang", "intent", "expect"), FIXTURES, ids=[f[0][:30] for f in FIXTURES])
def test_constraints_extracted(text: str, lang: str, intent: str, expect: dict) -> None:  # type: ignore[type-arg]
    d = detect(text, today=TODAY)
    for k, v in expect.items():
        assert getattr(d.constraints, k) == v, (k, getattr(d.constraints, k))


def test_attachment_implies_audit() -> None:
    d = detect("Check if this hike is good today", has_attachment=True, today=TODAY)
    assert d.intent is Intent.audit and d.constraints.date == TODAY.isoformat()
    assert detect("route.gpx", today=TODAY).intent is Intent.audit


def test_selection_and_help() -> None:
    assert detect("2", today=TODAY).selection == 2
    assert detect("the second one", today=TODAY).selection == 2
    assert detect("la première", today=TODAY, lang_hint="fr").selection == 1
    assert detect("hi", today=TODAY).intent is Intent.help
    assert detect("Salut !", today=TODAY).intent is Intent.help


def test_language_detection() -> None:
    assert detect_language("Wanderung morgen im Kanton Uri") == "de"
    assert detect_language("Randonnée demain près de Sion") == "fr"
    assert detect_language("Escursione domani vicino a Bellinzona") == "it"
    assert detect_language("Hike tomorrow near Interlaken") == "en"


def test_dates() -> None:
    assert detect("hike on Saturday near Zug", today=TODAY).constraints.date == "2026-09-12"
    assert detect("Wanderung am 3.10. bei Chur", today=TODAY).constraints.date == "2026-10-03"
    assert detect("rando après-demain près de Sion", today=TODAY).constraints.date == "2026-09-11"
