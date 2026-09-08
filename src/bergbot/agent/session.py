"""One conversation. Deterministic orchestration of the workflows with the register rule applied; the LLM
(when a key exists) refines low-confidence intents, verifies statuses on the web, finds media and answers
free questions. Files (report, GPX) are written to `workdir`; the Reply carries their paths."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bergbot.conversation.intent import Detection, detect
from bergbot.conversation.media import is_famous, media_query_spec
from bergbot.conversation.message import (
    render_audit_message,
    render_candidates_message,
    render_check_message,
    render_emergency,
    render_help,
)
from bergbot.conversation.qa import answer
from bergbot.conversation.register import decide
from bergbot.conversation.replanning import apply_modifier, merge
from bergbot.conversation.suggestions import suggest
from bergbot.core.domain import (
    AmenityStatus,
    Audit,
    CandidateSet,
    ChatMessage,
    Constraint,
    Evidence,
    EvidenceClass,
    Intent,
    Media,
    QuestionKind,
    Register,
)
from bergbot.core.geospatial.export import export_route
from bergbot.core.reporting.render import render_report
from bergbot.core.workflows import audit_route, run_around, run_audit, run_check, run_find
from bergbot.i18n import Lang, load, normalise_lang
from bergbot.sources.http import Fetcher

ProgressCb = Callable[[str], None]


@dataclass
class Reply:
    message: ChatMessage
    files: list[Path] = field(default_factory=list)
    audit: Audit | None = None
    candidates: CandidateSet | None = None
    lines_for_llm: list[str] = field(default_factory=list)


@dataclass
class Session:
    workdir: Path
    lang: Lang | None = None
    fetcher: Fetcher | None = None
    offline: bool = False
    llm: Any = None  # bergbot.agent.llm.LLM or None
    with_map: bool = True
    audit: Audit | None = None
    candidates: CandidateSet | None = None
    constraints: Constraint = field(default_factory=Constraint)
    history: list[dict[str, str]] = field(default_factory=list)
    last_lang: Lang = "en"
    _reports: dict[str, Path] = field(default_factory=dict)

    # ---------- entry point ----------
    def handle(self, text: str, attachment: Path | None = None, progress: ProgressCb | None = None) -> Reply:
        progress = progress or (lambda _s: None)
        det = detect(text, has_attachment=attachment is not None, lang_hint=self.lang or self.last_lang)
        if self.lang:
            det.lang = self.lang
        if (
            det.confidence < 0.75
            and det.intent not in (Intent.emergency,)
            and self.llm is not None
            and getattr(self.llm, "available", False)
        ):
            det = self._refine(det, text)
        self.last_lang = det.lang
        L = load(det.lang)
        self.history.append({"role": "user", "content": text})
        reply = self._dispatch(det, text, attachment, progress, L)
        self.history.append({"role": "assistant", "content": reply.message.text})
        return reply

    def _refine(self, det: Detection, text: str) -> Detection:
        try:
            obj = self.llm.classify(text, det.lang, datetime.now(tz=UTC).date().isoformat())
        except Exception:  # noqa: BLE001
            return det
        if not obj:
            return det
        try:
            det.intent = Intent(obj.get("intent", det.intent.value))
            det.lang = normalise_lang(obj.get("lang", det.lang))
            det.question = QuestionKind(obj.get("question", det.question.value))
            det.selection = obj.get("selection")
            c = Constraint.model_validate(obj.get("constraints") or {})
            det.constraints = merge(det.constraints, c)
            det.confidence = 0.9
        except Exception:  # noqa: BLE001
            return det
        return det

    # ---------- dispatch ----------
    def _dispatch(
        self, det: Detection, text: str, attachment: Path | None, progress: ProgressCb, L: Any
    ) -> Reply:
        lang = det.lang
        if det.intent is Intent.emergency:
            return Reply(render_emergency(lang))
        if det.intent is Intent.help:
            s = suggest(lang, region=self.constraints.region, month=None)
            return Reply(render_help(lang, [x.text for x in s]))
        if det.intent is Intent.audit:
            path = attachment or self._find_file(text)
            if path is None:
                return Reply(self._plain(L.t("ui.unknown_intent"), lang))
            return self._do_audit_file(path, det, progress, lang)
        if det.intent in (Intent.find, Intent.around):
            self.constraints = merge(self.constraints, det.constraints)
            return self._do_candidates(det, progress, lang)
        if det.intent is Intent.select:
            return self._do_select(det.selection or 1, progress, lang)
        if det.intent is Intent.modify:
            self.constraints = merge(self.constraints, det.constraints)
            self.constraints = apply_modifier(text, self.constraints)
            if self.candidates is not None or self.constraints.place or self.constraints.region:
                det.intent = (
                    Intent.around if (self.constraints.place and not self.constraints.region) else Intent.find
                )
                return self._do_candidates(det, progress, lang)
            return Reply(self._plain(L.t("ui.unknown_intent"), lang))
        if det.intent is Intent.export:
            return self._do_export(text, lang)
        if det.intent is Intent.media:
            return self._do_media(progress, lang)
        if det.intent is Intent.check:
            return self._do_check(text, det, progress, lang)
        return self._do_chat(text, det, lang)

    # ---------- workflows ----------
    def _do_audit_file(self, path: Path, det: Detection, progress: ProgressCb, lang: Lang) -> Reply:
        L = load(lang)
        progress(L.t("ui.progress.geometry"))
        c = merge(self.constraints, det.constraints)
        try:
            audit = run_audit(
                path,
                date=c.date,
                start_time=c.start_time or "09:00",
                lang=lang,
                offline=self.offline,
                fetcher=self.fetcher,
                origin=c.origin,
                constraints=c,
            )
        except Exception as e:  # noqa: BLE001
            return Reply(
                self._plain(
                    f"{L.t('safety.terms.could_not_verify', what=path.name)} ({type(e).__name__})", lang
                )
            )
        return self._finish_audit(audit, progress, lang)

    def _finish_audit(self, audit: Audit, progress: ProgressCb, lang: Lang, why: str | None = None) -> Reply:
        L = load(lang)
        famous, reason = is_famous(audit.route)
        audit.route.identity.famous = famous
        audit.route.identity.famous_reason = reason
        self._web_verify_amenities(audit, progress, lang)
        progress(L.t("ui.progress.rendering"))
        register = decide(audit, Intent.audit, QuestionKind.none)
        stem = _slug(audit.route.name) or "route"
        report = self.workdir / f"bergbot-report-{stem}.html"
        html, _warn = render_report(
            audit, lang=lang, with_map=self.with_map and not self.offline, fetcher=self.fetcher
        )
        report.write_text(html, encoding="utf-8")
        audit_json = self.workdir / f"bergbot-audit-{stem}.json"
        audit_json.write_text(audit.model_dump_json(by_alias=True, indent=1), encoding="utf-8")
        self.audit = audit
        self._reports[stem] = report
        msg = render_audit_message(audit, register, lang=lang, report_filename=report.name, why=why)
        return Reply(msg, files=[report], audit=audit)

    def _do_candidates(self, det: Detection, progress: ProgressCb, lang: Lang) -> Reply:
        L = load(lang)
        c = self.constraints
        c.lang = lang
        progress(L.t("ui.progress.resolving"))
        try:
            if det.intent is Intent.around or (c.place and not c.region):
                cs = run_around(
                    c.place or c.region or c.origin or "",
                    c,
                    lang=lang,
                    limit=3,
                    offline=self.offline,
                    fetcher=self.fetcher,
                )
            else:
                cs = run_find(c, lang=lang, limit=3, offline=self.offline, fetcher=self.fetcher)
        except LookupError as e:
            return Reply(self._plain(f"{L.t('ui.unknown_intent')} ({e})", lang))
        self.candidates = cs
        register = decide(_worst(cs), det.intent, det.question)
        return Reply(render_candidates_message(cs, register, lang=lang), candidates=cs)

    def _do_select(self, n: int, progress: ProgressCb, lang: Lang) -> Reply:
        L = load(lang)
        if not self.candidates or n < 1 or n > len(self.candidates.candidates):
            return Reply(self._plain(L.t("ui.unknown_intent"), lang))
        cand = self.candidates.candidates[n - 1]
        progress(L.t("ui.progress.closures"))
        c = self.candidates.constraints
        audit = audit_route(
            cand.route,
            date=c.date,
            start_time=c.start_time or "09:00",
            lang=lang,
            offline=self.offline,
            fetcher=self.fetcher,
            origin=c.origin,
            constraints=c,
        )
        why = _why_text(cand, L)
        return self._finish_audit(audit, progress, lang, why=why)

    def _do_export(self, text: str, lang: Lang) -> Reply:
        L = load(lang)
        if self.audit is None:
            return Reply(self._plain(L.t("ui.unknown_intent"), lang))
        fmt = (
            "kml"
            if re.search(r"\bkml\b", text, re.I)
            else "geojson"
            if re.search(r"geojson", text, re.I)
            else "gpx"
        )
        stem = _slug(self.audit.route.name) or "route"
        target = export_route(self.audit.route, fmt, self.workdir / f"bergbot-route-{stem}.{fmt}")
        lines = [
            L.t("ui.export.saved_to", kind=fmt.upper(), path=target.name),
            L.t("ui.export.swisstopo_line"),
        ]
        return Reply(
            ChatMessage(
                text="\n".join(lines),
                lines=lines,
                lang=lang,
                mode=Register.playful,
                attachments=[target.name],
                intent=Intent.export,
            ),
            files=[target],
        )

    def _do_media(self, progress: ProgressCb, lang: Lang) -> Reply:
        L = load(lang)
        if self.audit is None:
            return Reply(self._plain(L.t("ui.unknown_intent"), lang))
        register = decide(self.audit, Intent.media, QuestionKind.none)
        spec = media_query_spec(self.audit.route, lang)
        links: list[dict[str, Any]] = []
        if self.llm is not None and getattr(self.llm, "available", False):
            try:
                links = self.llm.media(spec, lang)
            except Exception:  # noqa: BLE001
                links = []
        if not links and spec.get("official_url"):
            links = [
                {
                    "title": self.audit.route.name,
                    "url": spec["official_url"],
                    "type": "official",
                    "date": None,
                    "description": None,
                }
            ]
        media = [
            Media(
                title=x["title"],
                url=x["url"],
                type=x.get("type")
                if x.get("type") in ("official", "gallery", "trip_report", "video", "article")
                else "article",
                date=x.get("date"),
                description=x.get("description"),
            )
            for x in links
        ]
        self.audit.media = media
        lines = [
            L.t("playful.media_intro")
            if register.mode is Register.playful
            else L.t("report.labels.third_party_note")
        ]
        lines += [f"• {m.title} — {m.url}" + (f" ({m.date})" if m.date else "") for m in media[:5]] or [
            L.t("report.labels.none_found")
        ]
        return Reply(
            ChatMessage(
                text="\n".join(lines[:12]),
                lines=lines[:12],
                lang=lang,
                mode=register.mode,
                intent=Intent.media,
            ),
            audit=self.audit,
        )

    def _do_check(self, text: str, det: Detection, progress: ProgressCb, lang: Lang) -> Reply:
        L = load(lang)
        kind, name = _check_subject(text, det)
        progress(L.t("ui.progress.lifts"))
        cr = run_check(kind, name, date=det.constraints.date, lang=lang, fetcher=self.fetcher)
        if self.llm is not None and getattr(self.llm, "available", False):
            try:
                wv = self.llm.verify(cr.web_verification_spec, lang)
            except Exception:  # noqa: BLE001
                wv = None
            if wv is not None:
                cr.evidence.insert(
                    0,
                    Evidence(
                        **{"class": EvidenceClass.A},
                        source=wv.url or "web",
                        url=wv.url,
                        retrieved_ts=datetime.now(tz=UTC),
                        original_span=wv.quoted_span,
                        translated_summary=wv.value,
                        verification=wv.result,
                    ),
                )
                cr.verification = wv.result
                if wv.result == "verified" and wv.value:
                    cr.status = (
                        AmenityStatus.closed
                        if wv.value in ("closed", "not_running", "ban", "winter_closure")
                        else AmenityStatus.open
                    )
                elif wv.result == "conflicting":
                    cr.status = AmenityStatus.conflicting
        return Reply(render_check_message(cr, lang=lang))

    def _do_chat(self, text: str, det: Detection, lang: Lang) -> Reply:
        L = load(lang)
        register = decide(self.audit, Intent.chat, det.question)
        qa = answer(text, self.audit, lang, det.question)
        facts = list(qa["facts"])
        if self.llm is not None and getattr(self.llm, "available", False):
            try:
                reply = self.llm.chat(text, lang, register.mode.value, facts, self.history[:-1])
            except Exception:  # noqa: BLE001
                reply = None
            if reply:
                lines = [ln for ln in reply.splitlines() if ln.strip()][:12]
                if det.question is QuestionKind.safety and L.t("safety.fixed_line") not in reply:
                    lines = (
                        (lines[:11] + [L.t("safety.fixed_line")])
                        if len(lines) >= 12
                        else lines + [L.t("safety.fixed_line")]
                    )
                return Reply(
                    ChatMessage(
                        text="\n".join(lines), lines=lines, lang=lang, mode=register.mode, intent=Intent.chat
                    )
                )
        if facts:
            lines = ([qa["frame"]] if qa.get("frame") else []) + facts
            return Reply(
                ChatMessage(
                    text="\n".join(lines[:12]),
                    lines=lines[:12],
                    lang=lang,
                    mode=register.mode,
                    intent=Intent.chat,
                )
            )
        fallback = (
            L.list("playful.chat_fallback")[0]
            if register.mode is Register.playful
            else L.t("ui.unknown_intent")
        )
        return Reply(self._plain(fallback, lang, register.mode))

    # ---------- helpers ----------
    def _web_verify_amenities(
        self, audit: Audit, progress: ProgressCb, lang: Lang, max_items: int = 2
    ) -> None:
        """Verify up to `max_items` lifts/huts with the LLM's web tool; results become verified evidence."""
        if self.llm is None or not getattr(self.llm, "available", False):
            return
        L = load(lang)
        done = 0
        t0 = time.monotonic()
        for w in list(audit.warnings):
            if (
                w.type.value not in ("lift_unverified", "hut_unverified")
                or done >= max_items
                or time.monotonic() - t0 > 60
            ):
                continue
            progress(L.t("ui.progress.lifts"))
            try:
                wv = self.llm.verify(w.params["web_verification"], lang)
            except Exception:  # noqa: BLE001
                wv = None
            done += 1
            if wv is None or wv.result != "verified" or not wv.value:
                continue
            for a in audit.amenities:
                if a.name == w.params.get("name"):
                    a.evidence.append(
                        Evidence(
                            **{"class": EvidenceClass.A},
                            source=wv.url or "web",
                            url=wv.url,
                            retrieved_ts=datetime.now(tz=UTC),
                            original_span=wv.quoted_span,
                            translated_summary=wv.value,
                            verification="verified",
                        )
                    )
                    a.verification = "verified"
                    a.status = (
                        AmenityStatus.closed if wv.value in ("closed", "not_running") else AmenityStatus.open
                    )
            if wv.value in ("closed", "not_running"):
                w.type = w.type.__class__("lift_closed") if w.type.value == "lift_unverified" else w.type
                w.severity = w.severity.__class__("important")
                w.params["source"] = wv.url or "web"
            else:
                audit.warnings.remove(w)
        audit.warnings.sort(key=lambda w: {"critical": 0, "important": 1, "note": 2}[w.severity.value])

    def _find_file(self, text: str) -> Path | None:
        m = re.search(r"([\w\-./ ]+\.(?:gpx|kml|geojson))", text, re.I)
        if not m:
            return None
        p = Path(m.group(1).strip())
        if p.exists():
            return p
        p2 = self.workdir / p.name
        return p2 if p2.exists() else None

    def _plain(self, text: str, lang: Lang, mode: Register = Register.serious) -> ChatMessage:
        lines = [ln for ln in text.splitlines() if ln.strip()][:12] or [text]
        return ChatMessage(text="\n".join(lines), lines=lines, lang=lang, mode=mode, intent=Intent.chat)


def _worst(cs: CandidateSet) -> Audit | None:
    """Register for a candidate list follows the worst candidate shown (warnings are never hidden)."""
    if not cs.candidates:
        return None
    ws = [w for c in cs.candidates[:3] for w in c.warnings]
    r = cs.candidates[0].route
    return Audit(
        route=r,
        date=cs.constraints.date or datetime.now(tz=UTC).date().isoformat(),
        generated_at=cs.generated_at,
        warnings=ws,
        lang=cs.lang,
    )


def _why_text(cand: Any, L: Any) -> str:
    bits = []
    w = cand.why or {}
    if w.get("named"):
        bits.append("SchweizMobil")
    if w.get("distance_from_place_m") is not None and w["distance_from_place_m"] < 1500:
        bits.append("≤ 1.5 km")
    if cand.weather_summary:
        main = cand.weather_summary.split("|")[0]
        bits.append(str(L.get(f"ui.weather_codes.{main}", main.replace("_", " "))))
    return " · ".join(bits) or "—"


def _check_subject(text: str, det: Detection) -> tuple[str, str]:
    low = text.lower()
    if re.search(r"fire|feuer|feu|fuoch", low):
        return "fire_ban", det.constraints.region or det.constraints.place or text
    kind = (
        "hut"
        if re.search(r"\b(hut|hütte|cabane|refuge|capanna|rifugio)\b", low)
        else "pass"
        if re.search(r"\b(pass|col|passo)\b", low)
        else "road"
        if re.search(r"\b(road|strasse|route|strada)\b", low)
        else "lift"
    )
    m = re.search(
        r"\b(?:the|die|der|das|le|la|il|l')\s+([A-ZÀ-Ý][\wÀ-ÿ\-']+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ\-']+){0,2})", text
    )
    name = m.group(1) if m else (det.constraints.place or text.strip("?! "))
    return kind, name


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


__all__ = ["Session", "Reply", "json"]
