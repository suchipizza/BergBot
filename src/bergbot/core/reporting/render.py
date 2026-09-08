"""Render the single-file HTML report (FR-H1..H9) from an `Audit`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from bergbot.brand import mascot_datauri, variant_for_activity
from bergbot.config import settings, utm
from bergbot.conversation.register import decide
from bergbot.core.domain import Audit, Evidence, Intent, QuestionKind, Severity
from bergbot.core.reporting.warnings_text import format_warning, severity_label, severity_marker
from bergbot.i18n import Locale, load, normalise_lang
from bergbot.sources.base import Query, SourceUnavailable
from bergbot.sources.http import Fetcher
from bergbot.ui.report.svg.map import render_map_svg
from bergbot.ui.report.svg.profile import render_profile_svg

TEMPLATES = Path(__file__).resolve().parents[2] / "ui" / "report" / "templates"
SIZE_WARN = 1_000_000
SIZE_FAIL = 2_000_000
TZ = ZoneInfo("Europe/Zurich")


class ReportTooLarge(RuntimeError):
    pass


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_report(
    audit: Audit, lang: str | None = None, with_map: bool = True, fetcher: Fetcher | None = None
) -> tuple[str, str | None]:
    lang_n = normalise_lang(lang or audit.lang)
    L = load(lang_n)
    register = decide(audit, Intent.audit, QuestionKind.none)
    tiles: dict[str, Any] | None = None
    map_note: str | None = None
    if with_map and not audit.offline:
        from bergbot.sources.ch.swisstopo_tiles import SwisstopoTilesAdapter
        from bergbot.ui.report.svg.map import padded_bbox

        try:
            rec = SwisstopoTilesAdapter(fetcher).fetch(
                Query(kind="map", bbox=padded_bbox(audit), params={"max_px": 1024})
            )[0]
            tiles = rec.payload
        except SourceUnavailable:
            map_note = L.t("report.labels.map_unavailable")
    else:
        map_note = L.t("report.labels.map_unavailable")

    warnings = [
        {
            "type": w.type.value,
            "severity": w.severity.value,
            "marker": severity_marker(w, L),
            "label": severity_label(w, L),
            "title": format_warning(w, L)[0],
            "body": format_warning(w, L)[1],
            "segment": w.affected_segment,
            "evidence": w.evidence,
            "original_text": w.original_text,
            "original_lang": w.original_lang,
            "web_verification": w.params.get("web_verification"),
        }
        for w in audit.warnings
    ]
    has_critical = any(w.severity is Severity.critical for w in audit.warnings)
    header_mascot = None
    if register.mascot_allowed and not has_critical:
        header_mascot = mascot_datauri(variant_for_activity(audit.route.activity.value))
    cfg = settings()
    ctx: dict[str, Any] = {
        "L": L,
        "t": L.t,
        "lang": lang_n,
        "audit": audit,
        "route": audit.route,
        "stats": audit.route.stats,
        "warnings": warnings,
        "fixed_line": L.t("safety.fixed_line"),
        "grade_text": _grade_text(audit, L),
        "duration_text": _duration(audit.route.stats.duration_min if audit.route.stats else 0, L),
        "map_svg": render_map_svg(audit, L, tiles),
        "map_note": map_note,
        "map_attribution": L.t("report.labels.map_attribution", attribution=tiles["attribution"])
        if tiles
        else None,
        "profile_svg": render_profile_svg(audit, L),
        "hours": _hours_table(audit),
        "conditions": audit.conditions,
        "transport": audit.transport,
        "amenities_by_kind": _group_amenities(audit),
        "escape_points": audit.escape_points,
        "evidence_rows": _evidence_rows(audit),
        "summary": audit.summary,
        "header_mascot": header_mascot,
        "footer_mascot": mascot_datauri("default"),
        "links": {
            "star": utm(cfg["github_url"], "report_footer"),
            "install": utm(cfg["website_url"].rstrip("/") + "/install/", "report_footer"),
            "waitlist": utm(cfg["waitlist_url"], "report_footer"),
        },
        "generated_at": audit.generated_at.astimezone(TZ).strftime("%d.%m.%Y %H:%M"),
        "date_text": _date_text(audit.date, lang_n),
        "version": audit.version,
        "register": register.mode.value,
        "fmt_time": lambda dt: dt.astimezone(TZ).strftime("%H:%M") if isinstance(dt, datetime) else "—",
        "fmt_ts": lambda dt: (
            dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M") if isinstance(dt, datetime) else "—"
        ),
        "term": lambda key: L.t(f"safety.terms.{key}"),
        "ev_label": lambda cls: L.t(f"safety.evidence_classes.{cls}.label"),
    }
    html = _env().get_template("report.html.j2").render(**ctx)
    size = len(html.encode("utf-8"))
    if size > SIZE_FAIL:
        raise ReportTooLarge(f"report is {size} bytes (> 2 MB)")
    warning = f"report is {size // 1024} KB (> 1 MB target)" if size > SIZE_WARN else None
    return html, warning


def _grade_text(audit: Audit, L: Locale) -> str:
    d = audit.route.difficulty
    if d.grade:
        return f"{d.grade} — {L.t(f'safety.t_grades.{d.grade}')}"
    return L.t("safety.not_graded")


def _duration(minutes: int, L: Locale) -> str:
    return L.t("ui.duration", h=minutes // 60, m=minutes % 60)


def _date_text(date: str, lang: str) -> str:
    try:
        d = datetime.fromisoformat(date)
    except ValueError:
        return date
    return d.strftime("%d.%m.%Y") if lang != "en" else d.strftime("%d %b %Y")


def _hours_table(audit: Audit) -> list[dict[str, Any]]:
    if not audit.conditions:
        return []
    rows = []
    for h in audit.conditions.hours:
        if not (audit.conditions.window_start <= h.time <= audit.conditions.window_end):
            continue
        rows.append(
            {
                "time": h.time.astimezone(TZ).strftime("%H:%M"),
                "km": h.km,
                "ele": h.elevation_m,
                "temp": f"{h.temp_c:.0f}" if h.temp_c is not None else "—",
                "precip": f"{h.precip_mm:.1f}" if h.precip_mm is not None else "—",
                "prob": f"{h.precip_prob:.0f}%" if h.precip_prob is not None else "",
                "wind": f"{h.wind_kmh:.0f}" if h.wind_kmh is not None else "—",
                "gust": f"{h.gust_kmh:.0f}" if h.gust_kmh is not None else "—",
                "summary": h.summary or "—",
                "storm": "⚡" if (h.thunder_prob or 0) >= 50 else "",
            }
        )
    return rows


def _group_amenities(audit: Audit) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for a in audit.amenities:
        out.setdefault(a.kind.value, []).append(a)
    return out


def _evidence_rows(audit: Audit) -> list[Evidence]:
    rows = []
    seen: set[tuple[str, str | None, str | None]] = set()
    all_ev = list(audit.evidence) + [e for w in audit.warnings for e in w.evidence]
    for e in all_ev:
        key = (e.source, e.url, e.translated_summary or e.original_span)
        if key in seen:
            continue
        seen.add(key)
        rows.append(e)
    return rows
