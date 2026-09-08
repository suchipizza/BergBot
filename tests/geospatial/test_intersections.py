"""Synthetic closures / zones intersecting a known route → correct km ranges."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from bergbot.core.domain import SegmentKind
from bergbot.core.geospatial.crs import to_wgs84
from bergbot.core.geospatial.ops import intersect_segments, is_loop, merge_segments, resample, route_bbox

E0, N0 = 2690000.0, 1200000.0


def line_ns(length_m: float, step: float = 25.0) -> list[list[float]]:
    return [list(to_wgs84(E0, N0 + i * step)) for i in range(int(length_m / step) + 1)]


def box(n_from: float, n_to: float, half_w: float = 50.0) -> dict:  # type: ignore[type-arg]
    corners = [
        (E0 - half_w, N0 + n_from),
        (E0 + half_w, N0 + n_from),
        (E0 + half_w, N0 + n_to),
        (E0 - half_w, N0 + n_to),
        (E0 - half_w, N0 + n_from),
    ]
    return {"type": "Polygon", "coordinates": [[list(to_wgs84(e, n)) for e, n in corners]]}


def test_polygon_intersection_km_range() -> None:
    coords = line_ns(5000)
    segs = intersect_segments(coords, box(1000, 2500), kind=SegmentKind.closure)
    assert len(segs) == 1
    assert abs(segs[0].from_km - 1.0) < 0.02 and abs(segs[0].to_km - 2.5) < 0.02


def test_line_closure_is_buffered() -> None:
    coords = line_ns(3000)
    closure = {
        "type": "LineString",
        "coordinates": [list(to_wgs84(E0 + 5, N0 + 500)), list(to_wgs84(E0 + 5, N0 + 900))],
    }
    segs = intersect_segments(coords, closure, kind=SegmentKind.closure)
    assert len(segs) == 1 and abs(segs[0].from_km - 0.5) < 0.03 and abs(segs[0].to_km - 0.9) < 0.03


def test_no_intersection() -> None:
    assert intersect_segments(line_ns(2000), box(3000, 4000)) == []


def test_multiple_and_merge() -> None:
    coords = line_ns(6000)
    a = intersect_segments(coords, box(500, 1000), kind=SegmentKind.zone, label="z")
    b = intersect_segments(coords, box(1020, 1500), kind=SegmentKind.zone, label="z")
    merged = merge_segments(a + b)
    assert len(merged) == 1 and merged[0].from_km < 0.52 and merged[0].to_km > 1.48


@settings(max_examples=25, deadline=None)
@given(st.floats(min_value=100, max_value=4000), st.floats(min_value=50, max_value=1500))
def test_hypothesis_range_inside_route(start: float, length: float) -> None:
    coords = line_ns(6000)
    segs = intersect_segments(coords, box(start, start + length))
    assert len(segs) == 1
    s = segs[0]
    assert 0 <= s.from_km <= s.to_km <= 6.0
    assert abs((s.to_km - s.from_km) * 1000 - length) < 30


def test_resample_and_bbox_and_loop() -> None:
    coords = line_ns(1000, step=200)
    rs = resample(coords, 25.0)
    assert 40 <= len(rs) <= 42
    bb = route_bbox(coords, pad_m=100)
    assert bb[0] < coords[0][0] < bb[2] and bb[1] < coords[0][1] < bb[3]
    assert not is_loop(coords)
    loop = coords + coords[::-1]
    assert is_loop(loop)
