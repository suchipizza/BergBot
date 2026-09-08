# 003 — Forecast source: MeteoSwiss ICON via Open-Meteo

MeteoSwiss publishes ICON-CH1/CH2-EPS as Open Government Data, but only as full-grid GRIB/NetCDF files on
data.geo.admin.ch (hundreds of MB per run). Downloading and decoding those on a laptop per audit would break
NFR-1. Open-Meteo re-serves exactly these MeteoSwiss models point-wise (`meteoswiss_icon_ch1`, `…_ch2`) under
CC-BY 4.0 with hourly resolution and elevation correction.

**Decision:** adapter `ch.meteoswiss` calls Open-Meteo with `models=meteoswiss_icon_ch1,meteoswiss_icon_ch2,
icon_seamless`. Attribution "© MeteoSchweiz · Weather data by Open-Meteo.com". Evidence class C.
MeteoSwiss natural-hazard warnings have no open machine-readable feed → web verification spec `natural_hazard`.
Revisit when MeteoSwiss ships a point forecast API.
