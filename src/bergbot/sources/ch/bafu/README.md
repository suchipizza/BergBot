# ch.bafu
Three adapters on BAFU GeoAdmin layers (OGD, © BAFU):
- `ch.bafu.quiet_zones` — wildlife quiet zones (`wrz-wildruhezonen_portal`): name, rule (R10 no access / R20 no
  access incl. winter sports / R30 marked paths only), protection period, legally binding flag. Cached 30 d.
- `ch.bafu.protected_areas` — Swiss parks zoning, federal hunting reserves, mire landscapes, Ramsar sites. 30 d.
- `ch.bafu.fire` — forest-fire danger level per warning region (`gefahren-waldbrand_warnung`, level parsed from
  the DE title: gering 1 … sehr gross 5) and cantonal prevention measures / fire bans. 1 h cache.
Cantonal fire bans not published in the layer are delegated to web verification (`shared.web` spec `fire_ban`).
