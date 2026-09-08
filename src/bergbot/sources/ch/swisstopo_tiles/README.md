# ch.swisstopo_tiles
swisstopo national map raster (`ch.swisstopo.pixelkarte-farbe`, WMTS EPSG:3857), stitched and cropped to the
route bbox as one JPEG ≤ 400 KB embedded in the report as a data URI. OGD, "© swisstopo" printed under the map.
Tiles are cached per user for 30 days and never bundled. On failure the report draws the route on a blank grid
and says so.
