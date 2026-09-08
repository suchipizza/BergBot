"""Forecast source. MeteoSwiss publishes ICON-CH1-EPS as Open Government Data (GRIB/NetCDF on data.geo.admin.ch);
open-meteo.com re-serves that model point-wise as `meteoswiss_icon_ch1` (33 h) with `icon_seamless` as fallback
for longer horizons. Bergbot samples the route at a few points/elevations and per hour of the time window.

Query kind `forecast`: bbox=(lon,lat,·,·) point, params.elevation_m, date, time_window.
Natural-hazard warnings (MeteoSwiss) have no open machine-readable feed at the time of writing → delegated to
web verification (shared.web spec `natural_hazard`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from bergbot.sources.base import Freshness, Health, Licence, Query, Record, SourceUnavailable
from bergbot.sources.http import Fetcher, default_fetcher

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
HOURLY = "temperature_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,weather_code,cloud_cover,snowfall,freezing_level_height"
DAILY = "sunrise,sunset"

WMO_CODES: dict[int, str] = {
    0: "clear",
    1: "mostly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "freezing_drizzle",
    57: "freezing_drizzle",
    61: "rain",
    63: "rain",
    65: "heavy_rain",
    66: "freezing_rain",
    67: "freezing_rain",
    71: "snow",
    73: "snow",
    75: "heavy_snow",
    77: "snow_grains",
    80: "showers",
    81: "showers",
    82: "heavy_showers",
    85: "snow_showers",
    86: "snow_showers",
    95: "thunderstorm",
    96: "thunderstorm_hail",
    99: "thunderstorm_hail",
}


class MeteoSwissAdapter:
    id = "ch.meteoswiss"
    kinds: ClassVar[tuple[str, ...]] = ("forecast",)
    ttl_s: ClassVar[int] = 1800

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher: Fetcher = fetcher or default_fetcher()
        self._last: datetime | None = None
        self._latency: int | None = None

    def fetch(self, query: Query) -> list[Record]:
        if query.kind != "forecast" or not query.bbox:
            raise ValueError("forecast needs kind=forecast and bbox point")
        lon, lat = query.bbox[0], query.bbox[1]
        elevation = query.params.get("elevation_m")
        days = int(query.params.get("forecast_days", 3))
        return [self.forecast(lon, lat, elevation_m=elevation, forecast_days=days)]

    def forecast(
        self, lon: float, lat: float, elevation_m: float | None = None, forecast_days: int = 3
    ) -> Record:
        params: dict[str, Any] = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "hourly": HOURLY,
            "daily": DAILY,
            "models": "meteoswiss_icon_ch1,meteoswiss_icon_ch2,icon_seamless",
            "forecast_days": forecast_days,
            "timezone": "Europe/Zurich",
        }
        if elevation_m is not None:
            params["elevation"] = int(elevation_m)
        res = self.fetcher.get_json(self.id, OPEN_METEO, params, ttl_s=self.ttl_s, what="weather forecast")
        self._last, self._latency = res.retrieved_ts, res.latency_ms
        d = res.data
        hourly = d.get("hourly", {})
        times = hourly.get("time", [])
        rows = []
        for i, t in enumerate(times):
            row = {"time": t}
            for key, col in (
                ("temp_c", "temperature_2m"),
                ("precip_mm", "precipitation"),
                ("precip_prob", "precipitation_probability"),
                ("wind_kmh", "wind_speed_10m"),
                ("gust_kmh", "wind_gusts_10m"),
                ("code", "weather_code"),
                ("cloud_pct", "cloud_cover"),
                ("snow_cm", "snowfall"),
                ("freezing_level_m", "freezing_level_height"),
            ):
                vals = _first_model(hourly, col)
                row[key] = vals[i] if vals and i < len(vals) else None
            code = row.get("code")
            row["summary"] = WMO_CODES.get(int(code), "unknown") if code is not None else None
            rows.append(row)
        daily = d.get("daily", {})
        return Record(
            source_id=self.id,
            kind="forecast",
            payload={
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
                "elevation_m": d.get("elevation"),
                "timezone": d.get("timezone"),
                "model": "MeteoSwiss ICON-CH1/CH2 via open-meteo",
                "hours": rows,
                "days": list(daily.get("time") or []),
                "sunrise": list(_first_model(daily, "sunrise") or []),
                "sunset": list(_first_model(daily, "sunset") or []),
            },
            source_ts=res.retrieved_ts,
            retrieved_ts=res.retrieved_ts,
            url=f"https://open-meteo.com/en/docs/meteoswiss-api?latitude={lat:.3f}&longitude={lon:.3f}",
            licence_note="MeteoSwiss ICON (OGD) via Open-Meteo (CC-BY 4.0)",
        )

    def freshness(self) -> Freshness:
        return Freshness(source_ts=self._last, retrieved_ts=self._last, ttl_s=self.ttl_s)

    def licence(self) -> Licence:
        return Licence(
            name="MeteoSwiss OGD (ICON-CH1/CH2) via Open-Meteo CC-BY 4.0",
            redistribution=True,
            attribution="© MeteoSchweiz · Weather data by Open-Meteo.com",
            url="https://open-meteo.com/en/docs/meteoswiss-api",
        )

    def health(self) -> Health:
        try:
            r = self.forecast(8.61, 46.99, 1500, forecast_days=1)
            return Health(ok=bool(r.payload["hours"]), latency_ms=self._latency, last_success_ts=self._last)
        except SourceUnavailable as e:
            return Health(ok=False, note=str(e))


def _first_model(block: dict[str, Any], col: str) -> list[Any] | None:
    """open-meteo returns `col` (single model) or `col_<model>` (multi-model). Merge per index: the first model
    (in request order: ICON-CH1 → ICON-CH2 → icon_seamless) that has a value for that hour wins, so the 33 h
    high-resolution horizon is used where available and the coarser model fills the rest."""
    if col in block:
        return list(block[col])
    cols = [list(v) for k, v in block.items() if k.startswith(col + "_") and v]
    if not cols:
        return None
    n = max(len(c) for c in cols)
    merged: list[Any] = []
    for i in range(n):
        val = None
        for c in cols:
            if i < len(c) and c[i] is not None:
                val = c[i]
                break
        merged.append(val)
    return merged


def now() -> datetime:
    return datetime.now(tz=UTC)
