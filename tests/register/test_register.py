"""FR-R2: 20 audits that must be serious, 20 that may be playful."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bergbot.conversation.register import decide
from bergbot.core.domain import (
    Audit,
    Evidence,
    EvidenceClass,
    Intent,
    QuestionKind,
    Register,
    Route,
    Severity,
    Warning,
    WarningType,
)

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)
EV = Evidence(**{"class": EvidenceClass.A}, source="t", retrieved_ts=NOW)
ROUTE = Route(geometry={"type": "LineString", "coordinates": [[8.6, 46.9], [8.7, 47.0]]})


def audit(*ws: tuple[WarningType, Severity]) -> Audit:
    return Audit(
        route=ROUTE,
        date="2026-09-09",
        generated_at=NOW,
        warnings=[Warning(type=t, severity=s, evidence=[EV]) for t, s in ws],
    )


MUST_BE_SERIOUS = [
    (audit((WarningType.trail_closure, Severity.critical)), Intent.audit, QuestionKind.none),
    (audit((WarningType.trail_closure, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.diversion, Severity.important)), Intent.audit, QuestionKind.none),
    (audit((WarningType.fire_restriction, Severity.note)), Intent.find, QuestionKind.none),
    (audit((WarningType.fire_danger, Severity.important)), Intent.find, QuestionKind.none),
    (audit((WarningType.shooting_activity, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.shooting_zone, Severity.important)), Intent.around, QuestionKind.none),
    (audit((WarningType.avalanche_context, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.exposed_wind, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.thunderstorm, Severity.important)), Intent.audit, QuestionKind.none),
    (audit((WarningType.heavy_precipitation, Severity.important)), Intent.find, QuestionKind.none),
    (audit((WarningType.guardian_dogs, Severity.important)), Intent.audit, QuestionKind.none),
    (audit((WarningType.wildlife_quiet_zone, Severity.important)), Intent.audit, QuestionKind.none),
    (audit((WarningType.transport_no_return, Severity.important)), Intent.audit, QuestionKind.none),
    (audit((WarningType.difficulty_above_ceiling, Severity.important)), Intent.find, QuestionKind.none),
    (
        audit((WarningType.long_day, Severity.note), (WarningType.lift_closed, Severity.important)),
        Intent.audit,
        QuestionKind.none,
    ),
    (audit(), Intent.emergency, QuestionKind.none),
    (None, Intent.emergency, QuestionKind.none),
    (audit(), Intent.chat, QuestionKind.safety),
    (audit((WarningType.long_day, Severity.note)), Intent.audit, QuestionKind.safety),
]

MAY_BE_PLAYFUL = [
    (audit(), Intent.audit, QuestionKind.none),
    (None, Intent.help, QuestionKind.none),
    (None, Intent.chat, QuestionKind.general),
    (None, Intent.find, QuestionKind.none),
    (audit((WarningType.long_day, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.lift_unverified, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.hut_unverified, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.source_unavailable, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.protected_area, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.wildlife_quiet_zone, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.heat, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.cold, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.snow_context, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.exposed_terrain, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.fire_danger, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.heavy_precipitation, Severity.note)), Intent.audit, QuestionKind.none),
    (audit((WarningType.shooting_zone, Severity.note)), Intent.audit, QuestionKind.none),
    (audit(), Intent.media, QuestionKind.none),
    (audit(), Intent.export, QuestionKind.none),
    (
        audit((WarningType.lift_unverified, Severity.note), (WarningType.long_day, Severity.note)),
        Intent.chat,
        QuestionKind.logistics,
    ),
]


@pytest.mark.parametrize(("a", "intent", "q"), MUST_BE_SERIOUS)
def test_must_be_serious(a: Audit | None, intent: Intent, q: QuestionKind) -> None:
    d = decide(a, intent, q)
    assert d.mode is Register.serious
    assert not d.mascot_allowed and not d.media_offer_allowed and not d.emoji_allowed
    assert d.reasons


@pytest.mark.parametrize(("a", "intent", "q"), MAY_BE_PLAYFUL)
def test_may_be_playful(a: Audit | None, intent: Intent, q: QuestionKind) -> None:
    d = decide(a, intent, q)
    assert d.mode is Register.playful
    assert d.mascot_allowed and d.media_offer_allowed and d.emoji_allowed


def test_counts() -> None:
    assert len(MUST_BE_SERIOUS) == 20 and len(MAY_BE_PLAYFUL) == 20
