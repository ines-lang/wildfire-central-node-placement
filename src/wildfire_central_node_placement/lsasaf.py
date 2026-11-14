"""LSA SAF FRP-PIXEL (SEVIRI, Meteosat 0 deg): the regions it covers."""
from wildfire_central_node_placement.registry import get_region

GEO_SOURCE = "lsasaf_msg0"            # the registry geo_source of the LSA SAF regions
SLOT_MIN = 15                          # SEVIRI repeat cycle


def lsasaf_region(region_id, registry=None):
    """Region entry; stops if the region does not use the LSA SAF GEO source (SEVIRI, Meteosat 0 deg)."""
    region = get_region(region_id, registry)
    if region["geo_source"] != GEO_SOURCE:
        raise SystemExit(f"Region '{region_id}' uses geo_source '{region['geo_source']}', not {GEO_SOURCE}: "
                         "not covered by LSA SAF.")
    return region
