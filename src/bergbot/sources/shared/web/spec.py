"""Web verification is performed by the LLM's web tool (plugin mode: the host agent; standalone: the Anthropic
web-search tool). This module only defines *what to search* and *what shape to return* (FR-D4). The core never
scrapes. Every verified status stores url, quoted span ≤ 15 words, timestamp and verified|unverified|conflicting.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

StatusType = Literal[
    "lift_status",
    "hut_open",
    "pass_open",
    "road_open",
    "fire_ban",
    "shooting_schedule",
    "natural_hazard",
    "media",
]


class WebVerification(BaseModel):
    """The only shape the LLM may hand back to core for a status."""

    status_type: StatusType
    subject: str
    date: str
    result: Literal["verified", "unverified", "conflicting"]
    value: str | None = Field(
        default=None,
        description="open | closed | running | not_running | ban | no_ban | level N | free text ≤ 10 words",
    )
    url: str | None = None
    quoted_span: str | None = Field(default=None, description="≤ 15 words verbatim from the page")
    page_ts: str | None = Field(default=None, description="Date on the page if stated (ISO)")
    retrieved_ts: str
    lang: str | None = None
    notes: str | None = None


VERIFICATION_SPECS: dict[str, dict[str, Any]] = {
    "lift_status": {
        "queries": [
            "{name} Betriebszeiten {date_de}",
            "{name} horaires d'ouverture {date_fr}",
            "{name} orari di apertura {date_it}",
            "{name} operating status {date_en}",
            "{name} Saisonstart Saisonende",
        ],
        "prefer": [
            "operator website",
            "schweizmobil.ch",
            "myswitzerland.com",
            "bergfex",
            "local tourism office",
        ],
        "verified_if": "an operator or official page states operation (dates/times) covering the date",
        "value_vocab": ["running", "not_running", "reduced"],
    },
    "hut_open": {
        "queries": [
            "{name} Hütte geöffnet {date_de}",
            "{name} cabane ouverte {date_fr}",
            "{name} capanna aperta {date_it}",
            "{name} SAC hut open {date_en}",
            "{name} site:sac-cas.ch",
        ],
        "prefer": ["hut website", "sac-cas.ch / huetten.sac-cas.ch", "hut Facebook/Instagram dated post"],
        "verified_if": "the hut's own page or the SAC portal states guarded/open dates covering the date",
        "value_vocab": ["open", "closed", "winter_room_only", "self_service"],
    },
    "pass_open": {
        "queries": [
            "{name} Pass offen {date_de}",
            "{name} col ouvert {date_fr}",
            "{name} passo aperto {date_it}",
            "{name} pass open TCS",
        ],
        "prefer": ["tcs.ch pass status", "cantonal road authority", "alpen-paesse.ch"],
        "verified_if": "TCS or cantonal page states open/closed for the date",
        "value_vocab": ["open", "closed", "winter_closure"],
    },
    "road_open": {
        "queries": [
            "{name} Strasse gesperrt {date_de}",
            "{name} route fermée {date_fr}",
            "{name} strada chiusa {date_it}",
        ],
        "prefer": ["cantonal road authority", "TCS"],
        "verified_if": "official page states status for the date",
        "value_vocab": ["open", "closed"],
    },
    "fire_ban": {
        "queries": [
            "Feuerverbot Kanton {canton_name} {date_de}",
            "interdiction de faire du feu canton {canton_name} {date_fr}",
            "divieto di accendere fuochi cantone {canton_name} {date_it}",
            "waldbrandgefahr.ch {canton_name}",
        ],
        "prefer": ["waldbrandgefahr.ch", "cantonal forestry office", "cantonal police"],
        "verified_if": "the cantonal or federal page states a ban or explicitly no measures for the date",
        "value_vocab": ["ban", "partial_ban", "no_ban"],
    },
    "shooting_schedule": {
        "queries": [
            "site:armee.ch/schiessanzeigen {notice_id}",
            "Schiessanzeige {name} {date_de}",
            "avis de tir {name} {date_fr}",
            "avviso di tiro {name} {date_it}",
        ],
        "prefer": ["armee.ch/schiessanzeigen/<id>"],
        "verified_if": "the notice lists the date (times) or shows no entry for that date",
        "value_vocab": ["shooting", "no_shooting"],
    },
    "natural_hazard": {
        "queries": [
            "MeteoSchweiz Warnungen {region} {date_de}",
            "MétéoSuisse avis {region} {date_fr}",
            "MeteoSvizzera allerte {region} {date_it}",
            "meteoswiss warnings {region}",
        ],
        "prefer": ["meteoswiss.admin.ch", "natural-hazards.ch"],
        "verified_if": "MeteoSwiss or the natural hazards portal shows a warning level for the area and date",
        "value_vocab": ["level 1", "level 2", "level 3", "level 4", "level 5", "none"],
    },
    "media": {
        "queries": [
            "{name} Wanderung Bericht",
            "{name} randonnée récit photos",
            "{name} escursione racconto foto",
            "{name} hike photos trip report",
            "{name} site:schweizmobil.ch",
            "{name} site:youtube.com",
        ],
        "prefer": [
            "official route page (schweizmobil.ch, tourism office)",
            "photo gallery",
            "recent dated trip report (hikr.org, blogs)",
            "video",
        ],
        "verified_if": "n/a — return 3–5 dated links with one-line descriptions; mark third_party=true",
        "value_vocab": [],
    },
}


def verification_spec(status_type: str, **fields: Any) -> dict[str, Any]:
    """Return the spec for `status_type` with query templates filled in where fields are known."""
    spec = VERIFICATION_SPECS[status_type]
    queries = []
    for q in spec["queries"]:
        try:
            queries.append(q.format(**{**_defaults(fields), **fields}))
        except KeyError:
            queries.append(q)
    return {
        "status_type": status_type,
        "queries": queries,
        "prefer": spec["prefer"],
        "verified_if": spec["verified_if"],
        "value_vocab": spec["value_vocab"],
        "output_schema": WebVerification.model_json_schema(),
        "rules": [
            "Quote at most 15 words verbatim from the page as quoted_span.",
            "Return 'unverified' when no page covers the date; never infer open/closed from absence.",
            "Return 'conflicting' when two credible pages disagree; include both URLs in notes.",
        ],
    }


def _defaults(fields: dict[str, Any]) -> dict[str, Any]:
    d = str(fields.get("date", ""))
    out: dict[str, Any] = {"date_de": d, "date_fr": d, "date_it": d, "date_en": d}
    try:
        from datetime import date as _date

        dt = _date.fromisoformat(d)
        out["date_de"] = dt.strftime("%d.%m.%Y")
        out["date_fr"] = dt.strftime("%d/%m/%Y")
        out["date_it"] = dt.strftime("%d.%m.%Y")
        out["date_en"] = dt.strftime("%d %B %Y")
    except ValueError:
        pass
    out.setdefault("name", fields.get("subject", ""))
    return out
