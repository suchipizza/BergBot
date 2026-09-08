"""Registry of all source adapters (used by `bergbot doctor` and workflows)."""

from __future__ import annotations

from bergbot.sources.base import SourceAdapter
from bergbot.sources.http import Fetcher


def all_adapters(fetcher: Fetcher | None = None) -> list[SourceAdapter]:
    from bergbot.sources.ch.army import ArmyShootingAdapter
    from bergbot.sources.ch.bafu import FireDangerAdapter, ProtectedAreasAdapter, QuietZonesAdapter
    from bergbot.sources.ch.closures import ClosuresAdapter
    from bergbot.sources.ch.geoadmin import GeoAdminAdapter
    from bergbot.sources.ch.guardian_dogs import GuardianDogsAdapter
    from bergbot.sources.ch.hiking_network import HikingNetworkAdapter, WanderlandRoutesAdapter
    from bergbot.sources.ch.meteoswiss import MeteoSwissAdapter
    from bergbot.sources.ch.slf import SLFAdapter
    from bergbot.sources.ch.swisstopo_tiles import SwisstopoTilesAdapter
    from bergbot.sources.ch.transport import TransportAdapter
    from bergbot.sources.shared.osm import OSMAdapter

    return [
        GeoAdminAdapter(fetcher),
        SwisstopoTilesAdapter(fetcher),
        HikingNetworkAdapter(fetcher),
        WanderlandRoutesAdapter(fetcher),
        ClosuresAdapter(fetcher),
        MeteoSwissAdapter(fetcher),
        QuietZonesAdapter(fetcher),
        ProtectedAreasAdapter(fetcher),
        FireDangerAdapter(fetcher),
        GuardianDogsAdapter(fetcher),
        ArmyShootingAdapter(fetcher),
        TransportAdapter(fetcher),
        SLFAdapter(fetcher),
        OSMAdapter(fetcher),
    ]
