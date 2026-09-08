"""Offline end-to-end audit on recorded fixtures: warnings ordered, evidence complete, JSON round-trips."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bergbot.core.domain import Audit, Severity, WarningType
from bergbot.core.workflows import run_audit
from bergbot.sources.http import FixtureFetcher

GPX = Path(__file__).resolve().parents[1] / "fixtures" / "gpx"
DATE = "2026-09-12"


def test_audit_waldstaetterweg(wf_fetcher: FixtureFetcher) -> None:
    a = run_audit(
        GPX / "waldstaetterweg-brunnen-vitznau.gpx",
        date=DATE,
        start_time="09:00",
        lang="de",
        fetcher=wf_fetcher,
        origin="Zürich HB",
    )
    assert a.route.stats and 14.0 < a.route.stats.distance_km < 14.9
    assert a.route.identity.name and "Waldst" in a.route.identity.name
    assert a.route.identity.famous  # national/regional SwitzerlandMobility route
    assert a.route.network_member
    types = [w.type for w in a.warnings]
    assert WarningType.trail_closure in types or WarningType.diversion in types
    assert WarningType.fire_danger in types
    # warnings sorted by severity, closure first
    sev = [w.severity for w in a.warnings]
    assert sev == sorted(
        sev, key=lambda s: {Severity.critical: 0, Severity.important: 1, Severity.note: 2}[s]
    )
    # every warning has evidence with retrieved_ts; closure has km range
    for w in a.warnings:
        assert w.evidence and all(e.retrieved_ts for e in w.evidence)
    closure = next(w for w in a.warnings if w.type in (WarningType.trail_closure, WarningType.diversion))
    assert closure.affected_segment and closure.affected_segment.to_km > closure.affected_segment.from_km
    assert closure.original_text  # verbatim German source text kept (FR-L3)
    # conditions & transport
    assert a.conditions and a.conditions.hours and a.conditions.sunset
    assert a.transport and a.transport.start_stop and a.transport.last_return
    assert a.transport.last_return.departure > a.conditions.window_end
    # amenities are unverified; summary lists lifts as unverified
    assert all(x.status.value == "unverified" for x in a.amenities)
    assert any(u.startswith("lift:") for u in a.summary.unverified)
    assert "closures" in a.summary.checked and "weather_wind" in a.summary.checked
    # round trip
    doc = json.loads(a.model_dump_json(by_alias=True))
    again = Audit.model_validate(doc)
    assert again.route.stats == a.route.stats


def test_audit_glarus_quiet_zone_and_park(wf_fetcher: FixtureFetcher) -> None:
    a = run_audit(GPX / "glarus-stage.gpx", date=DATE, lang="it", fetcher=wf_fetcher, origin="Zürich HB")
    types = {w.type for w in a.warnings}
    assert WarningType.wildlife_quiet_zone in types and WarningType.protected_area in types
    qz = next(w for w in a.warnings if w.type is WarningType.wildlife_quiet_zone)
    assert qz.severity is Severity.note  # September is outside the winter protection period
    assert qz.params["period"]


def test_audit_rigi_shooting_zone(wf_fetcher: FixtureFetcher) -> None:
    a = run_audit(GPX / "rigi-stage.gpx", date=DATE, lang="fr", fetcher=wf_fetcher, origin="Luzern")
    sz = next(w for w in a.warnings if w.type is WarningType.shooting_zone)
    assert sz.params["web_verification"]["status_type"] == "shooting_schedule"
    assert sz.affected_segment is not None


def test_offline_audit_degrades_loudly() -> None:
    a = run_audit(GPX / "synthetic-5km-400m.gpx", date=DATE, offline=True)
    assert a.offline
    assert a.route.stats and abs(a.route.stats.ascent_m - 400) < 20
    unavailable = {w.params["source"] for w in a.warnings if w.type is WarningType.source_unavailable}
    assert {"ch.closures", "ch.meteoswiss", "ch.transport"} <= unavailable
    assert a.summary.unverified


def test_cli_audit_json_is_valid_audit(tmp_path: Path) -> None:
    out = tmp_path / "audit.json"
    cmd = [
        sys.executable,
        "-m",
        "bergbot.cli",
        "audit",
        str(GPX / "synthetic-loop-4km.gpx"),
        "--date",
        DATE,
        "--offline",
        "--out",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    a = Audit.model_validate_json(out.read_text())
    assert a.route.is_loop and a.route.stats and a.route.stats.distance_km > 3.9
