# ch.meteoswiss
Hourly forecast (temperature, precipitation and probability, wind, gusts, WMO code, cloud, snowfall, freezing
level) plus sunrise/sunset. Model: MeteoSwiss ICON-CH1-EPS / ICON-CH2-EPS (OGD), served point-wise by
open-meteo.com (CC-BY 4.0) — see `docs/decisions/003-forecast-source.md`. Cached 30 min. Attribution:
"© MeteoSchweiz · Weather data by Open-Meteo.com". Natural-hazard warnings are not machine-readable in the
open feed and are delegated to web verification (`shared.web`, spec `natural_hazard`).
