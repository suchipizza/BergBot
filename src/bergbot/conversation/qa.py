"""FR-C5 follow-up questions answered from the Audit first: returns structured facts for the renderer/LLM.
Safety questions are framed by `safety.safety_answer_frame` (known / unknown / your call) — never a verdict."""

from __future__ import annotations

import re
from typing import Any

from bergbot.core.domain import Audit, QuestionKind, Severity
from bergbot.core.reporting.warnings_text import format_warning
from bergbot.i18n import load, normalise_lang

T_GRADE = re.compile(r"\bT\s?([1-6])\b", re.I)
WATER = re.compile(r"\b(water|wasser|eau|acqua)\b", re.I)
HUT = re.compile(r"\b(hut|hütte|cabane|capanna|restaurant|lunch|zmittag|repas|pranzo)\b", re.I)
TRANSPORT = re.compile(
    r"\b(train|bus|last|return|zug|letzte|rückfahrt|retour|dernier|treno|ultimo|ritorno)\b", re.I
)
WEATHER = re.compile(
    r"\b(weather|rain|wind|wetter|regen|météo|pluie|vent|meteo|pioggia|vento|temperature|temperatur)\b", re.I
)
IMPORT = re.compile(r"\b(import|swisstopo|komoot|gaia)\b", re.I)


def answer(
    question: str, audit: Audit | None, lang: str, question_kind: QuestionKind = QuestionKind.none
) -> dict[str, Any]:
    """Return {'kind', 'facts': [...lines], 'frame': str|None, 'register_hint'}. Facts are already localised."""
    L = load(normalise_lang(lang))
    q = question
    facts: list[str] = []
    m = T_GRADE.search(q)
    if m and not audit:
        facts.append(f"T{m.group(1)}: {L.t(f'safety.t_grades.T{m.group(1)}')}")
        return {"kind": "explain_grade", "facts": facts, "frame": None}
    if m:
        facts.append(f"T{m.group(1)}: {L.t(f'safety.t_grades.T{m.group(1)}')}")
    if audit is None:
        return {"kind": "general", "facts": facts, "frame": None}
    if WATER.search(q):
        water = [a for a in audit.amenities if a.kind.value == "water"]
        facts.append(
            f"{L.t('report.labels.water')}: "
            + (
                ", ".join(f"{a.name} (km {a.km})" for a in water[:6])
                if water
                else L.t("report.labels.none_found")
            )
        )
    if HUT.search(q):
        huts = [a for a in audit.amenities if a.kind.value in ("hut", "restaurant")]
        facts.append(
            f"{L.t('report.labels.huts')}: "
            + (
                ", ".join(f"{a.name} (km {a.km}, {L.t(f'safety.terms.{a.status.value}')})" for a in huts[:6])
                if huts
                else L.t("report.labels.none_found")
            )
        )
    if TRANSPORT.search(q) and audit.transport:
        t = audit.transport
        if t.last_return:
            facts.append(
                f"{L.t('report.labels.transport_back')}: {t.last_return.from_stop} {t.last_return.departure:%H:%M} → {t.last_return.to_stop} {t.last_return.arrival:%H:%M}"
            )
        else:
            facts.append(L.t("ui.message.transport_unavailable"))
    if WEATHER.search(q) and audit.conditions:
        from bergbot.conversation.message import weather_line

        facts.append(weather_line(audit, L))
    if IMPORT.search(q):
        facts.append(L.t("ui.export.swisstopo_line"))
    frame = None
    if question_kind is QuestionKind.safety:
        frame = L.t("safety.safety_answer_frame")
        known = [
            f"{L.t(f'ui.severity_marker.{w.severity.value}')} {format_warning(w, L)[0]}"
            for w in audit.warnings
            if w.severity in (Severity.critical, Severity.important)
        ]
        facts.append(
            f"{L.t('report.labels.summary_known')}: "
            + (", ".join(known) if known else L.t("report.labels.no_warnings"))
        )
        facts.append(
            f"{L.t('report.labels.summary_unverified')}: " + (", ".join(audit.summary.unverified[:5]) or "—")
        )
        s = audit.route.stats
        if s:
            facts.append(
                f"{audit.route.difficulty.grade or L.t('safety.not_graded')} · {s.distance_km} km · ↑{int(s.ascent_m)} m · {L.t('ui.duration', h=s.duration_min // 60, m=s.duration_min % 60)}"
            )
        facts.append(L.t("safety.fixed_line"))
    if not facts:
        return {"kind": "general", "facts": [], "frame": None}
    return {"kind": "from_audit", "facts": facts, "frame": frame}
