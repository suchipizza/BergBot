"""ch.meteoswiss — hourly forecast along the route from MeteoSwiss ICON-CH1/CH2 (served through open-meteo.com)."""

from bergbot.sources.ch.meteoswiss.adapter import WMO_CODES, MeteoSwissAdapter

__all__ = ["MeteoSwissAdapter", "WMO_CODES"]
