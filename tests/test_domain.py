from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from bergbot.core.domain import (
    Amenity,
    AmenityKind,
    AmenityStatus,
    Audit,
    ChatMessage,
    Evidence,
    EvidenceClass,
    Route,
    Severity,
    Warning,
    WarningType,
)

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def ev(**kw: object) -> Evidence:
    base = {"class": EvidenceClass.A, "source": "test", "retrieved_ts": NOW}
    base.update(kw)  # type: ignore[arg-type]
    return Evidence.model_validate(base)


def test_warning_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        Warning(type=WarningType.trail_closure, severity=Severity.critical, evidence=[])


def test_evidence_span_limit() -> None:
    with pytest.raises(ValidationError):
        ev(original_span=" ".join(["w"] * 16))
    assert ev(original_span=" ".join(["w"] * 15)).original_span


def test_evidence_has_retrieved_ts() -> None:
    with pytest.raises(ValidationError):
        Evidence.model_validate({"class": "A", "source": "x"})


def test_amenity_never_open_without_verification() -> None:
    with pytest.raises(ValidationError):
        Amenity(kind=AmenityKind.hut, name="H", lon=8.0, lat=46.0, status=AmenityStatus.open)
    ok = Amenity(
        kind=AmenityKind.hut,
        name="H",
        lon=8.0,
        lat=46.0,
        status=AmenityStatus.open,
        verification="verified",
        evidence=[ev()],
    )
    assert ok.status is AmenityStatus.open
    default = Amenity(kind=AmenityKind.hut, name="H", lon=8.0, lat=46.0)
    assert default.status is AmenityStatus.unverified


def test_audit_sorts_warnings_by_severity() -> None:
    r = Route(geometry={"type": "LineString", "coordinates": [[8.0, 46.0], [8.1, 46.1]]})
    a = Audit(
        route=r,
        date="2026-09-09",
        generated_at=NOW,
        warnings=[
            Warning(type=WarningType.long_day, severity=Severity.note, evidence=[ev()]),
            Warning(type=WarningType.trail_closure, severity=Severity.critical, evidence=[ev()]),
            Warning(type=WarningType.heat, severity=Severity.important, evidence=[ev()]),
        ],
    )
    assert [w.severity for w in a.warnings] == [Severity.critical, Severity.important, Severity.note]


def test_chat_message_max_12_lines() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(text="x", lines=["l"] * 13, lang="en", mode="playful")


@given(st.sampled_from(list(WarningType)), st.sampled_from(list(Severity)))
def test_every_warning_has_evidence_with_timestamps(wt: WarningType, sev: Severity) -> None:
    w = Warning(type=wt, severity=sev, evidence=[ev(source_ts=NOW)])
    assert w.evidence and all(e.retrieved_ts for e in w.evidence)
    d = w.model_dump(mode="json", by_alias=True)
    assert d["evidence"][0]["class"] == "A"
    assert Warning.model_validate(d).type is wt
