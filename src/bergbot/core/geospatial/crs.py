"""Coordinate transforms WGS84 ↔ LV95 (EPSG:2056). All metric operations in core run in LV95."""

from __future__ import annotations

from functools import lru_cache

from pyproj import Transformer


@lru_cache(maxsize=1)
def _to_lv95() -> Transformer:
    return Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)


@lru_cache(maxsize=1)
def _to_wgs() -> Transformer:
    return Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)


def to_lv95(lon: float, lat: float) -> tuple[float, float]:
    e, n = _to_lv95().transform(lon, lat)
    return float(e), float(n)


def to_wgs84(e: float, n: float) -> tuple[float, float]:
    lon, lat = _to_wgs().transform(e, n)
    return float(lon), float(lat)
