from __future__ import annotations

import argparse
import tempfile
from datetime import date
from pathlib import Path
from uuid import UUID

import numpy as np
from pystac_client import Client
from rasterio.enums import Resampling

from satellite_worker.config import settings
from satellite_worker.db import (
    satellite_scene_is_handled_for_metrics,
    save_satellite_metrics,
    save_satellite_observation,
)
from satellite_worker.multisource_raster import (
    build_grid_from_asset,
    build_metric_result,
    read_asset_to_grid,
    sign_planetary_computer_item,
)
from satellite_worker.raster_storage import (
    publish_metric_rasters,
)
from satellite_worker.storage_context import (
    get_field_storage_context,
)
from satellite_worker.storage_manifests import (
    write_satellite_manifest_from_database,
)


SAR_METRIC_TYPES = (
    "sar_vv_db",
    "sar_vh_db",
    "sar_vv_vh_ratio",
    "sar_rvi",
)


def calculate_sar_metric_arrays(
    *,
    vv: np.ndarray,
    vh: np.ndarray,
) -> dict[str, np.ndarray]:
    """
    Derive radar metrics from linear Sentinel-1 RTC gamma-naught power.
    """
    with np.errstate(
        divide="ignore",
        invalid="ignore",
    ):
        return {
            "sar_vv_db":
                10.0
                * np.log10(
                    vv
                ),
            "sar_vh_db":
                10.0
                * np.log10(
                    vh
                ),
            "sar_vv_vh_ratio":
                vv
                / vh,
            "sar_rvi":
                4.0
                * vh
                / (
                    vv
                    + vh
                ),
        }


def search_sentinel1_rtc(
    *,
    geometry: dict,
    start_date: date,
    end_date: date,
    limit: int,
):
    catalog = Client.open(
        settings
        .planetary_computer_stac_url
    )

    search = catalog.search(
        collections=[
            "sentinel-1-rtc"
        ],
        intersects=geometry,
        datetime=(
            f"{start_date.isoformat()}"
            "/"
            f"{end_date.isoformat()}"
        ),
    )

    items = list(
        search.items()
    )

    items = [
        item
        for item in items
        if (
            "vv" in item.assets
            and "vh" in item.assets
        )
    ]

    items.sort(
        key=lambda item: (
            item.datetime
            or item.common_metadata
            .start_datetime
        ),
        reverse=True,
    )

    if limit > 0:
        items = items[
            :limit
        ]

    return items


def process_scene(
    *,
    item,
    field_id: UUID,
    context: dict,
    geometry: dict,
    output_directory: Path,
) -> None:
    signed_item = (
        sign_planetary_computer_item(
            item
        )
    )

    grid = build_grid_from_asset(
        item=signed_item,
        field_geometry=geometry,
        asset_key="vv",
    )

    (
        vv,
        vv_invalid,
        _,
    ) = read_asset_to_grid(
        item=signed_item,
        grid=grid,
        asset_key="vv",
        resampling=(
            Resampling.bilinear
        ),
    )

    (
        vh,
        vh_invalid,
        _,
    ) = read_asset_to_grid(
        item=signed_item,
        grid=grid,
        asset_key="vh",
        resampling=(
            Resampling.bilinear
        ),
    )

    valid = (
        grid.inside_field
        & ~vv_invalid
        & ~vh_invalid
        & np.isfinite(
            vv
        )
        & np.isfinite(
            vh
        )
        & (
            vv > 0
        )
        & (
            vh > 0
        )
    )

    metric_arrays = (
        calculate_sar_metric_arrays(
            vv=vv,
            vh=vh,
        )
    )

    native_resolution = float(
        item.properties.get(
            "sar:pixel_spacing_range"
        )
        or grid.resolution_m
    )

    definitions = (
        (
            "sar_vv_db",
            metric_arrays["sar_vv_db"],
            "10*log10(VV_gamma0)",
            "dB",
        ),
        (
            "sar_vh_db",
            metric_arrays["sar_vh_db"],
            "10*log10(VH_gamma0)",
            "dB",
        ),
        (
            "sar_vv_vh_ratio",
            metric_arrays["sar_vv_vh_ratio"],
            "VV_gamma0/VH_gamma0",
            "ratio",
        ),
        (
            "sar_rvi",
            metric_arrays["sar_rvi"],
            "4*VH_gamma0/(VV_gamma0+VH_gamma0)",
            "unitless",
        ),
    )

    results = []

    for (
        metric_type,
        values,
        formula,
        unit,
    ) in definitions:
        result = build_metric_result(
            metric_type=(
                metric_type
            ),
            values=values,
            valid_mask=valid,
            grid=grid,
            output_directory=(
                output_directory
            ),
            scene_id=item.id,
            native_resolution_m=(
                native_resolution
            ),
            formula_version=(
                formula
            ),
            source_name=(
                "planetary-computer-"
                "sentinel-1-rtc"
            ),
            calibration_methods={
                "vv":
                    "RTC gamma0",
                "vh":
                    "RTC gamma0",
            },
            metadata_json={
                "unit":
                    unit,
                "radar_source":
                    "Sentinel-1 RTC",
            },
        )

        if result is not None:
            results.append(
                result
            )

    observed_on = (
        item.datetime.date()
    )

    observation_metadata = {
        "processing_version":
            "sentinel1-rtc-metrics-v1",
        "processing_status":
            (
                "metrics_processed"
                if results
                else
                "skipped_no_usable_pixels"
            ),
        "stac_item_id":
            item.id,
        "stac_collection":
            item.collection_id,
        "datetime":
            item.datetime.isoformat(),
        "platform":
            item.properties.get(
                "platform"
            ),
        "constellation":
            item.properties.get(
                "constellation"
            ),
        "orbit_state":
            item.properties.get(
                "sat:orbit_state"
            ),
        "relative_orbit":
            item.properties.get(
                "sat:relative_orbit"
            ),
        "instrument_mode":
            item.properties.get(
                "sar:instrument_mode"
            ),
        "polarizations":
            item.properties.get(
                "sar:polarizations"
            ),
        "cloud_independent":
            True,
        "field_valid_pixel_percent":
            (
                float(
                    valid.sum()
                )
                / grid.pixel_count
                * 100.0
            ),
    }

    observation_id = (
        save_satellite_observation(
            field_id=field_id,
            observed_on=(
                observed_on
            ),
            scene_id=item.id,
            cloud_cover_percent=None,
            metadata_json=(
                observation_metadata
            ),
            source=(
                "sentinel-1-rtc"
            ),
        )
    )

    if not results:
        write_satellite_manifest_from_database(
            context=context,
            observation_id=(
                observation_id
            ),
        )

        print(
            "No usable Sentinel-1 "
            "pixels over the field; "
            "scene recorded as handled."
        )

        return

    raster_uris = (
        publish_metric_rasters(
            context=context,
            observed_on=(
                observed_on
            ),
            observation_id=(
                observation_id
            ),
            results=results,
        )
    )

    save_satellite_metrics(
        observation_id=(
            observation_id
        ),
        results=results,
        raster_uris=(
            raster_uris
        ),
    )

    write_satellite_manifest_from_database(
        context=context,
        observation_id=(
            observation_id
        ),
    )

    print(
        "Radar metrics saved: "
        + ", ".join(
            result.metric_type
            .upper()
            for result in results
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Sentinel-1 RTC all-weather "
            "radar metrics for one field."
        )
    )

    parser.add_argument(
        "--field-id",
        required=True,
    )

    parser.add_argument(
        "--start",
        required=True,
    )

    parser.add_argument(
        "--end",
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
    )

    args = parser.parse_args()

    field_id = UUID(
        args.field_id
    )

    start_date = date.fromisoformat(
        args.start
    )

    end_date = date.fromisoformat(
        args.end
    )

    context = (
        get_field_storage_context(
            field_id
        )
    )

    geometry = context[
        "field_boundary"
    ]

    print(
        "Searching Sentinel-1 RTC..."
    )

    items = search_sentinel1_rtc(
        geometry=geometry,
        start_date=start_date,
        end_date=end_date,
        limit=args.limit,
    )

    print(
        f"Found {len(items)} dual-pol radar scenes."
    )

    failed_scenes = 0

    for item in items:
        if item.datetime is None:
            continue

        if (
            args.skip_existing
            and satellite_scene_is_handled_for_metrics(
                field_id=field_id,
                scene_id=item.id,
                metric_types=(
                    SAR_METRIC_TYPES
                ),
            )
        ):
            print(
                "Skipping already-ingested "
                f"radar scene: {item.id}"
            )

            continue

        print()
        print(
            "=================================="
        )
        print(
            f"Radar scene: {item.id}"
        )
        print(
            f"Date: {item.datetime.date()}"
        )

        with tempfile.TemporaryDirectory(
            prefix=(
                f"farm-s1-"
                f"{field_id}-"
            )
        ) as temporary:
            try:
                process_scene(
                    item=item,
                    field_id=field_id,
                    context=context,
                    geometry=geometry,
                    output_directory=(
                        Path(
                            temporary
                        )
                    ),
                )

            except Exception as error:
                failed_scenes += 1

                print(
                    "FAILED radar scene: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

    if failed_scenes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
