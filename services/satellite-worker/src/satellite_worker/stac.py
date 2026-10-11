from datetime import date

import pystac
from pystac_client import Client

from satellite_worker.config import (
    settings,
)


RED_ASSET_NAMES = (
    "red",
    "B04",
    "b04",
)


NIR_ASSET_NAMES = (
    "nir",
    "B08",
    "b08",
)


SCL_ASSET_NAMES = (
    "scl",
    "SCL",
)


def get_asset(
    item: pystac.Item,
    candidates: tuple[str, ...],
) -> pystac.Asset:

    for candidate in candidates:

        asset = item.assets.get(candidate)

        if asset is not None:
            return asset

    raise RuntimeError(
        "Unable to find one of "
        f"{candidates} in STAC item "
        f"{item.id}. "
        f"Available assets: "
        f"{sorted(item.assets.keys())}"
    )


def search_sentinel2(
    *,
    geometry: dict,
    start_date: date,
    end_date: date,
    max_scene_cloud: float = 60,
    limit: int = 20,
) -> list[pystac.Item]:

    catalog = Client.open(settings.earth_search_url)

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        intersects=geometry,
        datetime=(f"{start_date.isoformat()}" "/" f"{end_date.isoformat()}"),
        query={
            "eo:cloud_cover": {
                "lt": max_scene_cloud,
            }
        },
    )

    items = list(search.items())

    items.sort(key=lambda item: (item.datetime or item.common_metadata.start_datetime))

    if limit > 0:
        items = items[:limit]

    return items
