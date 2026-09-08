"""FR-C5: constraint diff → which core steps must rerun."""

from __future__ import annotations

from bergbot.core.domain import Constraint

STEP_FOR_FIELD = {
    "date": {"conditions", "logistics", "zones", "rank"},
    "start_time": {"conditions", "logistics", "rank"},
    "region": {"candidates"},
    "place": {"candidates"},
    "start_place": {"candidates"},
    "end_place": {"candidates"},
    "origin": {"logistics", "rank"},
    "max_travel_min": {"logistics", "rank"},
    "transport_required": {"logistics", "rank"},
    "max_ascent_m": {"filter", "rank"},
    "max_distance_km": {"filter", "rank"},
    "min_distance_km": {"filter", "rank"},
    "max_duration_min": {"filter", "rank"},
    "max_grade": {"filter", "rank"},
    "loop": {"filter", "rank"},
    "hut": {"amenities", "rank"},
    "restaurant": {"amenities", "rank"},
    "water": {"amenities"},
    "dog": {"zones", "filter", "rank"},
    "bivouac": {"zones"},
    "kids": {"filter", "rank"},
    "seniors": {"filter", "rank"},
    "activity": {"candidates"},
}


def merge(old: Constraint, delta: Constraint) -> Constraint:
    """Apply non-null fields of `delta` on top of `old` (free_text/lang always taken from delta)."""
    data = old.model_dump()
    for k, v in delta.model_dump().items():
        if v is not None and k not in ("free_text", "lang"):
            data[k] = v
    data["free_text"] = delta.free_text
    data["lang"] = delta.lang or old.lang
    return Constraint.model_validate(data)


def steps_to_rerun(old: Constraint, new: Constraint) -> set[str]:
    steps: set[str] = set()
    for k, v in new.model_dump().items():
        if k in ("free_text", "lang"):
            continue
        if v != getattr(old, k):
            steps |= STEP_FOR_FIELD.get(k, {"candidates"})
    if "candidates" in steps:
        steps |= {"filter", "rank", "zones", "conditions", "logistics", "amenities"}
    return steps


def apply_modifier(text: str, old: Constraint) -> Constraint:
    """Relative modifications ('shorter', 'less climb', 'easier') that have no explicit number."""
    low = text.lower()
    c = old.model_copy()
    if any(w in low for w in ("shorter", "kürzer", "plus court", "più cort")):
        base = old.max_distance_km or 12.0
        c.max_distance_km = round(base * 0.7, 1)
    if any(w in low for w in ("longer", "länger", "plus long", "più lung")):
        base = old.max_distance_km or 12.0
        c.max_distance_km = round(base * 1.4, 1)
    if any(
        w in low
        for w in (
            "less climb",
            "flatter",
            "weniger",
            "moins de dénivelé",
            "meno dislivello",
            "easier",
            "einfacher",
            "leichter",
            "plus facile",
            "più facile",
        )
    ):
        base = old.max_ascent_m or 800.0
        c.max_ascent_m = round(base * 0.7)
        if c.max_grade in (None, "T3", "T4", "T5", "T6"):
            c.max_grade = "T2"
    if any(w in low for w in ("harder", "schwerer", "plus dur", "più dur")):
        base = old.max_ascent_m or 600.0
        c.max_ascent_m = round(base * 1.4)
    return c
