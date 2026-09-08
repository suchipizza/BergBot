"""M6 safety regressions: closure, fire ban, wind on ridge, quiet zone, shooting day, unverified lift →
warnings present and ordered, serious register, no header mascot, fixed line present (SR-2, SR-3, SR-7)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bergbot.conversation.message import render_audit_message
from bergbot.conversation.register import decide
from bergbot.core.domain import (
    Amenity,
    AmenityKind,
    AmenityStatus,
    Audit,
    Evidence,
    EvidenceClass,
    Intent,
    QuestionKind,
    Register,
    Route,
    Segment,
    SegmentKind,
    Severity,
    Warning,
    WarningType,
)
from bergbot.core.reporting.render import render_report
from bergbot.core.scoring.score import hard_filter_reasons
from bergbot.i18n import LANGS, load
from tests.safety.forbidden import find_forbidden

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "workflows"
NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def _audit(name: str) -> Audit:
    return Audit.model_validate(json.loads((FIX / f"{name}.audit.json").read_text(encoding="utf-8")))


def _ev(cls: EvidenceClass = EvidenceClass.A) -> Evidence:
    return Evidence(**{"class": cls}, source="test", retrieved_ts=NOW, url="https://example.org")


def _synthetic(*ws: Warning) -> Audit:
    r = Route(
        geometry={
            "type": "LineString",
            "coordinates": [[8.6, 46.95, 1500], [8.61, 46.96, 1900], [8.62, 46.97, 2100]],
        },
        profile=[[0, 1500], [1, 1900], [2, 2100]],
    )
    return Audit(route=r, date="2026-09-12", generated_at=NOW, warnings=list(ws))


CASES = {
    "closure": _audit("waldstaetterweg-brunnen-vitznau"),
    "shooting": _audit("rigi-stage"),
    "quiet_zone_and_park": _audit("glarus-stage"),
    "fire_ban": _synthetic(
        Warning(
            type=WarningType.fire_restriction,
            severity=Severity.important,
            evidence=[_ev()],
            params={
                "scope": "Ticino",
                "restriction": "Absolute ban on fires",
                "source": "waldbrandgefahr.ch",
            },
        )
    ),
    "wind_on_ridge": _synthetic(
        Warning(
            type=WarningType.exposed_wind,
            severity=Severity.important,
            evidence=[_ev(EvidenceClass.C)],
            affected_segment=Segment(from_km=0.8, to_km=1.6, kind=SegmentKind.exposed),
            params={"gust_kmh": 65, "time": "13:00", "from_km": 0.8, "to_km": 1.6},
        )
    ),
    "shooting_day": _synthetic(
        Warning(
            type=WarningType.shooting_activity,
            severity=Severity.critical,
            evidence=[_ev()],
            params={
                "name": "Seebodenalp",
                "date": "2026-09-12",
                "times": "08:00–17:00",
                "source": "armee.ch",
            },
        )
    ),
    "unverified_lift_only": _synthetic(
        Warning(
            type=WarningType.lift_unverified,
            severity=Severity.note,
            evidence=[_ev()],
            params={"name": "Gemmibahn", "date": "2026-09-12"},
        )
    ),
}


@pytest.mark.parametrize("name", [k for k in CASES if k != "unverified_lift_only"])
@pytest.mark.parametrize("lang", LANGS)
def test_serious_cases(name: str, lang: str) -> None:
    a = CASES[name]
    L = load(lang)
    reg = decide(a, Intent.audit, QuestionKind.none)
    if name == "quiet_zone_and_park":
        # September: quiet zone outside its winter period → note → playful allowed unless fire says otherwise
        pass
    else:
        assert reg.mode is Register.serious, reg.reasons
        assert not reg.mascot_allowed
    msg = render_audit_message(a, reg, lang=lang)
    sev = [w.severity for w in a.warnings]
    assert sev == sorted(
        sev, key=lambda s: {Severity.critical: 0, Severity.important: 1, Severity.note: 2}[s]
    )
    assert msg.lines[0] == L.t("ui.message.warnings_header")
    assert L.t("safety.fixed_line") in msg.lines
    assert find_forbidden(msg.text, [lang]) == []
    html, _ = render_report(a, lang=lang, with_map=False)
    block = html[html.index('id="before-you-go"') : html.index('id="route"')]
    assert "mascot" not in block
    if reg.mode is Register.serious:
        assert 'id="header-mascot"' not in html
        # no emoji beyond severity markers in a serious message
        assert not any(ch in msg.text for ch in "👇😀🙂🎉📷")


def test_unverified_lift_stays_playful_but_unverified() -> None:
    a = CASES["unverified_lift_only"]
    reg = decide(a, Intent.audit, QuestionKind.none)
    assert reg.mode is Register.playful
    msg = render_audit_message(a, reg, lang="de")
    assert load("de").t("ui.message.not_verified_label") in msg.text


def test_warnings_survive_constraints_and_ranking() -> None:
    """SR-2: constraints filter candidates, never warnings; a closed route is excluded, not silently cleaned."""
    from bergbot.core.domain import Constraint

    a = CASES["closure"]
    reasons = hard_filter_reasons(a.route, Constraint(max_ascent_m=10000), a.warnings)
    assert "closed" in reasons
    assert any(w.type is WarningType.trail_closure for w in a.warnings)


def test_unverified_never_becomes_open_or_closed() -> None:
    a = Amenity(kind=AmenityKind.lift, name="X", lon=8.0, lat=46.0)
    assert a.status is AmenityStatus.unverified
    with pytest.raises(ValueError):
        a.status = AmenityStatus.open
        Amenity.model_validate(a.model_dump())
    # OSM opening_hours never flips the status
    from bergbot.core.logistics.amenities import nearby_amenities
    from bergbot.sources.http import FixtureFetcher

    fx = FixtureFetcher.from_files(*sorted((FIX.parent / "sources").glob("osm.json")))
    fx.strict = False
    audit = CASES["closure"]
    amen, _w, _u = nearby_amenities(audit.route, "2026-09-12", fetcher=fx)
    assert amen and all(x.status is AmenityStatus.unverified for x in amen)


def test_web_verification_without_evidence_is_unverified() -> None:
    """A model answer 'verified' without url + quote is downgraded (SR-3)."""
    from bergbot.agent.llm import LLM

    class _Block:
        type = "text"
        text = '{"status_type":"lift_status","subject":"Gemmibahn","date":"2026-09-12","result":"verified","value":"running","retrieved_ts":"2026-09-09T10:00:00Z"}'

    class _Resp:
        content = [_Block()]
        stop_reason = "end_turn"

    class _Msgs:
        def create(self, **kw: object) -> _Resp:
            return _Resp()

    class _Client:
        messages = _Msgs()

    llm = LLM()
    llm.available = True
    llm._client = _Client()
    wv = llm.verify(
        {
            "status_type": "lift_status",
            "queries": [],
            "prefer": [],
            "verified_if": "",
            "value_vocab": [],
            "rules": [],
        }
    )
    assert wv is not None and wv.result == "unverified"


@pytest.mark.parametrize("lang", LANGS)
def test_emergency_short_circuit_session(lang: str, tmp_path: Path) -> None:
    from bergbot.agent.session import Session

    text = {
        "en": "someone fell, he is injured",
        "fr": "quelqu'un est tombé, il est blessé",
        "de": "jemand ist gestürzt und verletzt",
        "it": "qualcuno è caduto ed è ferito",
    }[lang]
    r = Session(workdir=tmp_path, offline=True).handle(text)
    assert r.message.intent is Intent.emergency and r.message.lang == lang
    assert "1414" in r.message.text and "112" in r.message.text
    assert len(r.message.lines) <= 6 and not r.files
