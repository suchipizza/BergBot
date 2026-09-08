"""Transport plan: nearest stops to start and end; outbound from `origin` arriving before the planned start;
last return from the end stop after planned end + margin. A timetable never verifies a lift."""

from __future__ import annotations

from datetime import datetime, timedelta

from bergbot.core.domain import (
    Evidence,
    EvidenceClass,
    Place,
    PlaceKind,
    Severity,
    TransportLeg,
    TransportPlan,
    Warning,
    WarningType,
)
from bergbot.sources.base import SourceUnavailable
from bergbot.sources.ch.transport import TransportAdapter
from bergbot.sources.http import Fetcher

MARGIN_MIN = 30


def plan_transport(
    start: Place,
    end: Place,
    date: str,
    start_time: str,
    planned_end: datetime,
    origin: str | None,
    fetcher: Fetcher | None = None,
    offline: bool = False,
) -> tuple[TransportPlan, list[Warning], list[Place]]:
    plan = TransportPlan(origin=origin)
    warnings: list[Warning] = []
    escape: list[Place] = []
    if offline:
        plan.unavailable = True
        return plan, warnings, escape
    t = TransportAdapter(fetcher)
    try:
        s_stops = t.stops_near(start.lon, start.lat)
        e_stops = t.stops_near(end.lon, end.lat)
    except SourceUnavailable:
        plan.unavailable = True
        return plan, warnings, escape
    s_stop = _pick(s_stops)
    e_stop = _pick(e_stops)
    plan.start_stop = s_stop["name"] if s_stop else None
    plan.end_stop = e_stop["name"] if e_stop else None
    for st in (s_stops + e_stops)[:6]:
        if st.payload.get("distance_m") is not None and st.payload["distance_m"] <= 1500:
            escape.append(
                Place(
                    name=st.payload["name"],
                    kind=PlaceKind.stop,
                    lon=st.payload["lon"],
                    lat=st.payload["lat"],
                    source="ch.transport",
                )
            )
    if s_stop:
        plan.evidence.append(
            Evidence(
                **{"class": EvidenceClass.A},
                source="ch.transport",
                retrieved_ts=s_stops[0].retrieved_ts,
                translated_summary=f"nearest stop to start: {s_stop['name']} ({round(s_stop.get('distance_m') or 0)} m)",
            )
        )
    if origin and s_stop:
        try:
            outs = t.connections(origin, s_stop["name"], date, start_time, is_arrival_time=True, limit=4)
            legs = [_leg(c.payload, c.url) for c in outs]
            legs = [lg for lg in legs if lg.arrival <= _local(date, start_time) + timedelta(minutes=5)]
            if legs:
                plan.outbound = legs[-1]
                plan.evidence.append(
                    Evidence(
                        **{"class": EvidenceClass.A},
                        source="ch.transport",
                        url=plan.outbound.url,
                        retrieved_ts=outs[0].retrieved_ts,
                        translated_summary=f"outbound {plan.outbound.from_stop} {plan.outbound.departure:%H:%M} → {plan.outbound.to_stop} {plan.outbound.arrival:%H:%M}",
                    )
                )
        except SourceUnavailable:
            plan.unavailable = True
    if e_stop:
        dest = origin or (s_stop["name"] if s_stop and s_stop["name"] != e_stop["name"] else None)
        if dest:
            try:
                after = t.connections(e_stop["name"], dest, date, planned_end.strftime("%H:%M"), limit=6)
                late = t.connections(e_stop["name"], dest, date, "21:30", limit=6)
                legs = [_leg(c.payload, c.url) for c in after + late]
                same_day = [
                    lg
                    for lg in legs
                    if lg.departure.date().isoformat() == date and lg.departure >= planned_end
                ]
                if same_day:
                    plan.last_return = max(same_day, key=lambda lg: lg.departure)
                    first = min(same_day, key=lambda lg: lg.departure)
                    plan.evidence.append(
                        Evidence(
                            **{"class": EvidenceClass.A},
                            source="ch.transport",
                            url=plan.last_return.url,
                            retrieved_ts=after[0].retrieved_ts if after else late[0].retrieved_ts,
                            translated_summary=f"last return {plan.last_return.from_stop} {plan.last_return.departure:%H:%M} → {plan.last_return.to_stop}",
                        )
                    )
                    if (plan.last_return.departure - planned_end) < timedelta(minutes=MARGIN_MIN):
                        warnings.append(
                            Warning(
                                type=WarningType.transport_tight_return,
                                severity=Severity.important,
                                evidence=plan.evidence[-1:],
                                params={
                                    "stop": e_stop["name"],
                                    "time": plan.last_return.departure.strftime("%H:%M"),
                                    "arrival": planned_end.strftime("%H:%M"),
                                },
                            )
                        )
                    _ = first
                else:
                    warnings.append(
                        Warning(
                            type=WarningType.transport_no_return,
                            severity=Severity.important,
                            evidence=[
                                Evidence(
                                    **{"class": EvidenceClass.B},
                                    source="ch.transport",
                                    retrieved_ts=(after or late)[0].retrieved_ts
                                    if (after or late)
                                    else _now(),
                                    translated_summary="no same-day return connection found after planned end",
                                )
                            ],
                            params={
                                "stop": e_stop["name"],
                                "time": planned_end.strftime("%H:%M"),
                                "date": date,
                            },
                        )
                    )
            except SourceUnavailable:
                plan.unavailable = True
    return plan, warnings, escape


def _pick(stops: list) -> dict | None:  # type: ignore[type-arg]
    for s in stops:
        if s.payload.get("id"):
            return dict(s.payload)
    return None


def _leg(p: dict, url: str | None) -> TransportLeg:  # type: ignore[type-arg]
    return TransportLeg(
        from_stop=p["from"],
        to_stop=p["to"],
        departure=datetime.fromisoformat(p["departure"]),
        arrival=datetime.fromisoformat(p["arrival"]),
        products=list(p.get("products") or []),
        changes=int(p.get("transfers") or 0),
        url=url,
    )


def _local(date: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{date}T{hhmm}:00+02:00")


def _now() -> datetime:
    from datetime import UTC

    return datetime.now(tz=UTC)
