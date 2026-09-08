from __future__ import annotations

from bergbot.core.domain import Constraint, Route, Warning, WarningType

GRADE_RANK = {"T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5, "T6": 6}


def hard_filter_reasons(route: Route, c: Constraint, warnings: list[Warning]) -> list[str]:
    """Return why a candidate fails hard constraints (empty = passes). Warnings are never reasons to hide a
    route except where the user's own constraint makes it unusable (dog + guardian dogs, closure on route)."""
    s = route.stats
    reasons: list[str] = []
    if s is None:
        return ["no_stats"]
    if c.max_ascent_m is not None and s.ascent_m > c.max_ascent_m * 1.05:
        reasons.append("ascent")
    if c.max_distance_km is not None and s.distance_km > c.max_distance_km * 1.05:
        reasons.append("distance")
    if c.min_distance_km is not None and s.distance_km < c.min_distance_km * 0.95:
        reasons.append("too_short")
    if c.max_duration_min is not None and s.duration_min > c.max_duration_min * 1.05:
        reasons.append("duration")
    if (
        c.max_grade
        and route.difficulty.grade
        and GRADE_RANK.get(route.difficulty.grade, 0) > GRADE_RANK.get(c.max_grade, 6)
    ):
        reasons.append("grade")
    if c.loop and not route.is_loop:
        reasons.append("loop")
    types = {w.type for w in warnings}
    if WarningType.trail_closure in types:
        reasons.append("closed")
    if c.dog and WarningType.guardian_dogs in types:
        reasons.append("guardian_dogs")
    return reasons


def soft_score(
    route: Route,
    c: Constraint,
    warnings: list[Warning],
    weather: dict[str, float | None],
    transport_ok: bool | None,
    proximity_m: float | None = None,
) -> tuple[float, dict[str, float]]:
    """0–100. Components: weather 40, transport 20, ascent fit 15, distance fit 15, difficulty fit 10.
    Deterministic; ties are broken by name upstream."""
    s = route.stats
    br: dict[str, float] = {}
    # weather
    w = 40.0
    precip = weather.get("precip_mm") or 0.0
    gust = weather.get("gust_kmh") or 0.0
    storm = weather.get("storm") or 0.0
    w -= min(20.0, precip * 2.0)
    w -= min(10.0, max(0.0, gust - 30.0) / 4.0)
    w -= 15.0 if storm else 0.0
    br["weather"] = max(0.0, w)
    # transport — or, while ranking without timetables, proximity of the route to the asked place
    if transport_ok is not None:
        br["transport"] = 20.0 if transport_ok else 0.0
    elif proximity_m is not None:
        br["transport"] = 20.0 * max(0.0, 1.0 - max(0.0, proximity_m - 800.0) / 9000.0)
    else:
        br["transport"] = 10.0
    # fit
    if s:
        if c.max_ascent_m:
            br["ascent_fit"] = 15.0 * max(0.0, 1.0 - abs(s.ascent_m - 0.75 * c.max_ascent_m) / c.max_ascent_m)
        else:
            br["ascent_fit"] = 15.0 * max(0.0, 1.0 - max(0.0, s.ascent_m - 900.0) / 900.0)
        if c.max_distance_km:
            br["distance_fit"] = 15.0 * max(
                0.0, 1.0 - abs(s.distance_km - 0.75 * c.max_distance_km) / c.max_distance_km
            )
        else:
            br["distance_fit"] = 15.0 * max(0.0, 1.0 - abs(s.distance_km - 12.0) / 12.0)
    else:
        br["ascent_fit"] = br["distance_fit"] = 0.0
    g = GRADE_RANK.get(route.difficulty.grade or "", 0)
    want = GRADE_RANK.get(c.max_grade or "", 0)
    br["difficulty_fit"] = 10.0 if not want or (g and g <= want) else 5.0 if not g else 0.0
    # named routes are easier to follow / share: small bonus
    br["named"] = 3.0 if route.identity.network == "ch.astra.wanderland" else 0.0
    total = round(sum(br.values()), 2)
    return total, br
