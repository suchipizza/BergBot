"""≤12-line chat message renderer (FR-M1–M3), both registers, four locales, plain text + minimal markdown.

Order for audit: warnings → route line → weather line → transport line → why → attachment → closing question.
For find/around: intro → 2–3 candidates × 2 lines → pick-one line. Serious register: no humour, no mascot, only
severity markers as emoji."""

from __future__ import annotations

import random
from datetime import datetime
from zoneinfo import ZoneInfo

from bergbot.core.domain import (
    Audit,
    CandidateSet,
    ChatMessage,
    CheckResult,
    Intent,
    Register,
    RegisterDecision,
    Severity,
    WarningType,
)
from bergbot.core.reporting.warnings_text import format_warning
from bergbot.i18n import Locale, load, normalise_lang

TZ = ZoneInfo("Europe/Zurich")
MAX_WARN_LINES = 4


def _pick(L: Locale, key: str, seed: str | None = None) -> str:
    opts = L.list(key)
    rng = random.Random(seed) if seed else random
    return str(rng.choice(opts))


def _duration(minutes: int, L: Locale) -> str:
    return L.t("ui.duration", h=minutes // 60, m=minutes % 60)


def _grade(audit: Audit, L: Locale) -> str:
    return audit.route.difficulty.grade or L.t("safety.not_graded")


def warning_lines(audit: Audit, L: Locale, max_lines: int = 3) -> list[str]:
    """Warnings first, severity ordered. Up to `max_lines` full lines; further warnings are folded into one
    line by title (nothing is dropped); unverified lifts/huts and unavailable sources go on a separate line.
    The fixed line always closes the block."""
    lines: list[str] = []
    shown = 0
    more: list[tuple[Severity, str]] = []
    unverified: list[str] = []
    for w in audit.warnings:
        if w.type in (
            WarningType.lift_unverified,
            WarningType.hut_unverified,
            WarningType.source_unavailable,
        ):
            unverified.append(str(w.params.get("name") or w.params.get("what") or w.type.value))
            continue
        title, body = format_warning(w, L)
        if shown >= max_lines:
            more.append((w.severity, title))
            continue
        seg = f" km {w.affected_segment.from_km}–{w.affected_segment.to_km}" if w.affected_segment else ""
        lines.append(f"{L.t(f'ui.severity_marker.{w.severity.value}')} {title}{seg}: {body}")
        shown += 1
    if more:
        worst = more[0][0]
        titles = ", ".join(dict.fromkeys(t for _, t in more))
        lines.append(f"{L.t(f'ui.severity_marker.{worst.value}')} +{len(more)}: {titles}")
    if unverified:
        lines.append(
            f"{L.t('ui.severity_marker.note')} {L.t('ui.message.not_verified_label')}: {', '.join(dict.fromkeys(unverified))}"
        )
    if lines:
        lines.insert(0, L.t("ui.message.warnings_header"))
        lines.append(L.t("safety.fixed_line"))
    return lines


def route_line(audit: Audit, L: Locale) -> str:
    s = audit.route.stats
    if not s:
        return audit.route.name
    return L.t(
        "ui.message.route_line",
        name=audit.route.name,
        grade=_grade(audit, L),
        distance_km=f"{s.distance_km:g}",
        ascent_m=int(s.ascent_m),
        descent_m=int(s.descent_m),
        duration=_duration(s.duration_min, L),
        start=(
            audit.transport.start_stop
            if audit.transport and audit.transport.start_stop
            else audit.route.start.name
            if audit.route.start
            else "?"
        ),
        end=(
            audit.transport.end_stop
            if audit.transport and audit.transport.end_stop
            else audit.route.end.name
            if audit.route.end
            else "?"
        ),
    )


def weather_line(audit: Audit, L: Locale) -> str:
    c = audit.conditions
    if not c or not c.hours:
        return L.t("ui.message.weather_unavailable")
    hs = [h for h in c.hours if c.window_start <= h.time <= c.window_end] or c.hours
    temps = [h.temp_c for h in hs if h.temp_c is not None]
    codes = [h.summary for h in hs if h.summary]
    main = max(set(codes), key=codes.count) if codes else "unknown"
    return L.t(
        "ui.message.weather_line",
        date=_date_text(audit.date, L.lang),
        summary=weather_word(main, L),
        temp_min=round(min(temps)) if temps else "—",
        temp_max=round(max(temps)) if temps else "—",
        gust_kmh=round(max((h.gust_kmh or 0) for h in hs)),
    )


def transport_line(audit: Audit, L: Locale) -> str:
    t = audit.transport
    if not t or t.unavailable:
        return L.t("ui.message.transport_unavailable")
    if not (t.outbound or t.last_return):
        if t.start_stop:
            return L.t("ui.message.transport_stop_only", stop=t.start_stop)
        return L.t("ui.message.transport_unavailable")
    if not t.outbound and t.last_return:
        lr = t.last_return
        return L.t(
            "ui.message.transport_return_only",
            ret_dep=_hm(lr.departure),
            ret_from=lr.from_stop,
            ret_to=lr.to_stop,
            ret_arr=_hm(lr.arrival),
        )
    ob, back2 = t.outbound, t.last_return
    return L.t(
        "ui.message.transport_line",
        out_dep=_hm(ob.departure) if ob else "—",
        out_from=ob.from_stop if ob else (t.origin or "—"),
        out_arr=_hm(ob.arrival) if ob else "—",
        out_to=ob.to_stop if ob else (t.start_stop or "—"),
        ret_dep=_hm(back2.departure) if back2 else "—",
        ret_from=back2.from_stop if back2 else (t.end_stop or "—"),
    )


def closing_question(audit: Audit, L: Locale, register: RegisterDecision) -> str:
    if audit.route.identity.famous and register.media_offer_allowed:
        return L.t("ui.message.closing_question_media")
    return L.t("ui.message.closing_question")


def render_audit_message(
    audit: Audit,
    register: RegisterDecision,
    lang: str | None = None,
    report_filename: str = "bergbot-report.html",
    why: str | None = None,
) -> ChatMessage:
    L = load(normalise_lang(lang or audit.lang))
    lines = warning_lines(audit, L)
    lines.append(route_line(audit, L))
    lines.append(weather_line(audit, L))
    lines.append(transport_line(audit, L))
    if why:
        lines.append(L.t("ui.message.why_line", reason=why))
    checked = ", ".join(x.replace("_", " ") for x in audit.summary.checked[:6]) or "—"
    unverified = ", ".join(audit.summary.unverified[:4])
    if len(lines) + 3 <= 12:
        lines.append(
            L.t("ui.message.audit_summary", checked=checked, unverified=unverified)
            if unverified
            else L.t("ui.message.audit_summary_all_checked", checked=checked)
        )
    lines.append(L.t("ui.message.attachment_line", filename=report_filename))
    lines.append(closing_question(audit, L, register))
    lines = _fit(lines, 12)
    buttons = _buttons(L, audit, register)
    return ChatMessage(
        text="\n".join(lines),
        lines=lines,
        lang=L.lang,
        mode=register.mode,
        attachments=[report_filename],
        buttons=buttons,
        intent=Intent.audit,
    )


def render_candidates_message(
    cs: CandidateSet, register: RegisterDecision, lang: str | None = None
) -> ChatMessage:
    L = load(normalise_lang(lang or cs.lang))
    lines: list[str] = []
    if not cs.candidates:
        lines.append(L.t("ui.message.no_candidates"))
        return ChatMessage(
            text="\n".join(lines), lines=lines, lang=L.lang, mode=register.mode, intent=cs.intent
        )
    if register.mode is Register.playful:
        if cs.intent is Intent.around and cs.place:
            lines.append(_pick(L, "playful.around_intro", cs.place.name).format(place=cs.place.name))
        else:
            lines.append(_pick(L, "playful.found_intro_generic", cs.generated_at.isoformat()))
    else:
        lines.append(L.t("ui.message.warnings_header"))
    for i, c in enumerate(cs.candidates[:3], 1):
        s = c.route.stats
        top = [w for w in c.warnings if w.severity in (Severity.critical, Severity.important)]
        lines.append(
            L.t(
                "ui.message.candidate_line",
                n=i,
                name=c.route.name,
                grade=c.route.difficulty.grade or L.t("safety.not_graded"),
                distance_km=f"{s.distance_km:g}" if s else "—",
                ascent_m=int(s.ascent_m) if s else "—",
                duration=_duration(s.duration_min, L) if s else "—",
            )
        )
        weather = _weather_short(c.weather_summary, L)
        warn = "; ".join(
            f"{L.t(f'ui.severity_marker.{w.severity.value}')} {format_warning(w, L)[0]}" for w in top[:2]
        )
        lines.append(
            L.t(
                "ui.message.candidate_line_two",
                weather=weather,
                transport=warn or (c.transport_summary or ""),
            ).rstrip(" ·")
        )
    if register.mode is Register.serious:
        lines.append(L.t("safety.fixed_line"))
    lines.append(L.t("ui.message.pick_one"))
    lines = _fit(lines, 12)
    return ChatMessage(
        text="\n".join(lines),
        lines=lines,
        lang=L.lang,
        mode=register.mode,
        buttons=[str(i) for i in range(1, len(cs.candidates[:3]) + 1)],
        intent=cs.intent,
    )


def render_check_message(cr: CheckResult, lang: str | None = None) -> ChatMessage:
    L = load(normalise_lang(lang or cr.lang))
    if cr.verification == "verified" and cr.evidence:
        e = cr.evidence[0]
        line = L.t(
            "check.verified",
            name=cr.name,
            status=L.t(f"safety.terms.{cr.status.value}"),
            source=e.source,
            ts=_ts(e.source_ts or e.retrieved_ts),
        )
    elif cr.verification == "conflicting":
        line = L.t(
            "check.conflicting",
            name=cr.name,
            a=cr.evidence[0].source if cr.evidence else "—",
            b=cr.evidence[1].source if len(cr.evidence) > 1 else "—",
        )
    else:
        line = L.t("ui.check.unverified", name=cr.name, date=_date_text(cr.date, L.lang))
    lines = [line, L.t("safety.fixed_line")]
    return ChatMessage(
        text="\n".join(lines), lines=lines, lang=L.lang, mode=Register.serious, intent=Intent.check
    )


def render_emergency(lang: str) -> ChatMessage:
    L = load(normalise_lang(lang))
    lines = [f"🔴 {L.t('safety.emergency.title')}"] + [
        ln for ln in L.t("safety.emergency.body").strip().splitlines() if ln.strip()
    ]
    return ChatMessage(
        text="\n".join(lines), lines=lines, lang=L.lang, mode=Register.serious, intent=Intent.emergency
    )


def render_help(lang: str, suggestions: list[str]) -> ChatMessage:
    L = load(normalise_lang(lang))
    lines = (
        [L.t("ui.help.intro")]
        + [f"• {x}" for x in L.list("ui.help.can")][:6]
        + [L.t("suggestions.intro")]
        + [f"{i}. {s}" for i, s in enumerate(suggestions[:4], 1)]
    )
    lines = _fit(lines, 12)
    return ChatMessage(
        text="\n".join(lines),
        lines=lines,
        lang=L.lang,
        mode=Register.playful,
        buttons=list(suggestions[:4]),
        intent=Intent.help,
    )


def _buttons(L: Locale, audit: Audit, register: RegisterDecision) -> list[str]:
    b = ["GPX", "➕"]
    if audit.route.identity.famous and register.media_offer_allowed:
        b.append("📷")
    return b


def _fit(lines: list[str], n: int) -> list[str]:
    if len(lines) <= n:
        return lines
    # drop from the middle (summary/why lines), never the warnings header, route line, attachment or closing question
    keep_tail = 2
    head = lines[: n - keep_tail]
    return head + lines[-keep_tail:]


def _weather_short(summary: str | None, L: Locale) -> str:
    if not summary:
        return L.t("ui.message.weather_unavailable")
    parts = summary.split("|")
    if len(parts) != 4:
        return summary
    main, tmin, tmax, gust = parts
    return f"{weather_word(main, L)} {tmin}–{tmax} °C, {gust} km/h"


def weather_word(code: str, L: Locale) -> str:
    return str(L.get(f"ui.weather_codes.{code}", code.replace("_", " ")))


def _hm(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%H:%M")


def _ts(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")


def _date_text(d: str, lang: str) -> str:
    try:
        dt = datetime.fromisoformat(d)
    except ValueError:
        return d
    return dt.strftime("%d.%m.%Y") if lang != "en" else dt.strftime("%d %b")
