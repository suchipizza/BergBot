"""ch.bafu — wildlife quiet zones, protected areas, forest-fire danger and cantonal fire measures (GeoAdmin layers)."""

from bergbot.sources.ch.bafu.adapter import FireDangerAdapter, ProtectedAreasAdapter, QuietZonesAdapter

__all__ = ["FireDangerAdapter", "ProtectedAreasAdapter", "QuietZonesAdapter"]
