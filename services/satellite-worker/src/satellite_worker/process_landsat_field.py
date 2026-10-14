from __future__ import annotations

import argparse
import tempfile
from datetime import date
from pathlib import Path
from uuid import UUID

import numpy as np
from pystac_client import Client
from rasterio.enums import Resampling

from satellite_worker.anomaly import (
    detect_metric_anomalies,
)
from satellite_worker.config import settings
from satellite_worker.db import (
    replace_satellite_anomalies,
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


LANDSAT_METRIC_TYPES = (
    "lst_c",
)

QA_INVALID_BITS = (
    0,  # fill
    1,  # dilated cloud
    2,  # cirrus (unused on older sensors)
    3,  # cloud
    4,  # cloud shadow
    5,  # snow
)

QA_CLOUD_BITS = (
    1,
    2,
    3,
    4,
)


def search_landsat_l2(
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
            "landsat-c2-l2"
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
            "qa_pixel"
            in item.assets
            and (
                "lwir11"
                in item.assets
                or "lwir"
                in item.assets
            )
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


def _bit_set(
    values: np.ndarray,
    bit: int,
) -> np.ndarray:
    return (
        (
            values
            >> bit
        )
        & 1
    ).astype(
        bool
    )


def landsat_temperature_celsius(
    *,
    raw_temperature: np.ndarray,
    scale: float,
    offset: float,
) -> np.ndarray:
    return (
        raw_temperature
        * scale
        + offset
        - 273.15
    )


def landsat_qa_masks(
    qa: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
]:
    invalid = np.zeros(
        qa.shape,
        dtype=bool,
    )

    for bit in QA_INVALID_BITS:
        invalid |= (
            _bit_set(
                qa,
                bit,
            )
        )

    cloud = np.zeros(
        qa.shape,
        dtype=bool,
    )

    for bit in QA_CLOUD_BITS:
        cloud |= (
            _bit_set(
                qa,
                bit,
            )
        )

    return (
        invalid,
        cloud,
    )


def _asset_scale_offset(
    asset,
) -> tuple[
    float,
    float,
]:
    bands = (
        asset.extra_fields.get(
            "raster:bands"
        )
        or []
    )

    if bands:
        band = bands[
            0
        ]

        return (
            float(
                band.get(
                    "scale",
                    0.00341802,
                )
            ),
            float(
                band.get(
                    "offset",
                    149.0,
                )
            ),
        )

    return (
        0.00341802,
        149.0,
    )


def _native_resolution(
    asset,
    fallback: float,
) -> float:
    bands = (
        asset.extra_fields.get(
            "raster:bands"
        )
        or []
    )

    if bands:
        value = (
            bands[
                0
            ].get(
                "spatial_resolution"
            )
        )

        if value is not None:
            return float(
                value
            )

    return fallback


def process_scene(
    *,
    item,
    field_id: UUID,
    context: dict,
    geometry: dict,
    output_directory: Path,
    max_scene_cloud: float,
) -> None:
    observed_on = (
        item.datetime.date()
    )

    scene_cloud = (
        item.properties.get(
            "eo:cloud_cover"
        )
    )

    scene_cloud_percent = (
        float(
            scene_cloud
        )
        if scene_cloud
        is not None
        else None
    )

    base_metadata = {
        "processing_version":
            "landsat-lst-v1",
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
        "scene_cloud_cover_percent":
            scene_cloud_percent,
    }

    if (
        scene_cloud_percent
        is not None
        and scene_cloud_percent
        >= max_scene_cloud
    ):
        observation_id = (
            save_satellite_observation(
                field_id=field_id,
                observed_on=(
                    observed_on
                ),
                scene_id=item.id,
                cloud_cover_percent=(
                    scene_cloud_percent
                ),
                metadata_json={
                    **base_metadata,
                    "processing_status":
                        "skipped_scene_cloud_cover",
                    "skip_reason":
                        "scene_cloud_cover_threshold",
                    "scene_cloud_threshold_percent":
                        max_scene_cloud,
                },
                source=(
                    "landsat-c2-l2"
                ),
            )
        )

        write_satellite_manifest_from_database(
            context=context,
            observation_id=(
                observation_id
            ),
        )

        print(
            "Skipping cloudy Landsat scene: "
            f"{scene_cloud_percent:.1f}%."
        )

        return

    signed_item = (
        sign_planetary_computer_item(
            item
        )
    )

    temperature_key = (
        "lwir11"
        if "lwir11"
        in signed_item.assets
        else "lwir"
    )

    grid = build_grid_from_asset(
        item=signed_item,
        field_geometry=geometry,
        asset_key=(
            temperature_key
        ),
    )

    (
        raw_temperature,
        temperature_invalid,
        temperature_asset,
    ) = read_asset_to_grid(
        item=signed_item,
        grid=grid,
        asset_key=(
            temperature_key
        ),
        resampling=(
            Resampling.bilinear
        ),
    )

    (
        qa_raw,
        qa_invalid,
        _,
    ) = read_asset_to_grid(
        item=signed_item,
        grid=grid,
        asset_key="qa_pixel",
        resampling=(
            Resampling.nearest
        ),
    )

    qa = np.where(
        np.isfinite(
            qa_raw
        ),
        qa_raw,
        0,
    ).astype(
        np.uint16
    )

    (
        invalid_qa,
        field_cloud,
    ) = landsat_qa_masks(
        qa
    )

    valid = (
        grid.inside_field
        & ~temperature_invalid
        & ~qa_invalid
        & ~invalid_qa
        & np.isfinite(
            raw_temperature
        )
        & (
            raw_temperature
            > 0
        )
    )

    field_cloud_count = int(
        (
            grid.inside_field
            & field_cloud
        ).sum()
    )

    field_cloud_percent = (
        field_cloud_count
        / grid.pixel_count
        * 100.0
    )

    scale, offset = (
        _asset_scale_offset(
            temperature_asset
        )
    )

    temperature_c = (
        landsat_temperature_celsius(
            raw_temperature=(
                raw_temperature
            ),
            scale=scale,
            offset=offset,
        )
    )

    result = build_metric_result(
        metric_type="lst_c",
        values=temperature_c,
        valid_mask=valid,
        grid=grid,
        output_directory=(
            output_directory
        ),
        scene_id=item.id,
        native_resolution_m=(
            _native_resolution(
                temperature_asset,
                grid.resolution_m,
            )
        ),
        formula_version=(
            "Landsat_C2_L2_ST*"
            f"{scale}+{offset}-273.15"
        ),
        source_name=(
            "planetary-computer-"
            "landsat-c2-l2"
        ),
        calibration_methods={
            temperature_key:
                "USGS Collection 2 "
                "Level-2 surface temperature "
                "scale/offset",
            "qa_pixel":
                "QA_PIXEL bits 0-5 masked",
        },
        metadata_json={
            "unit":
                "degC",
            "field_cloud_cover_percent":
                field_cloud_percent,
        },
    )

    if result is None:
        observation_id = (
            save_satellite_observation(
                field_id=field_id,
                observed_on=(
                    observed_on
                ),
                scene_id=item.id,
                cloud_cover_percent=(
                    scene_cloud_percent
                ),
                metadata_json={
                    **base_metadata,
                    "processing_status":
                        "skipped_no_usable_pixels",
                    "skip_reason":
                        "landsat_qa_mask",
                    "field_cloud_cover_percent":
                        field_cloud_percent,
                    "field_usable_pixel_percent":
                        0.0,
                },
                source=(
                    "landsat-c2-l2"
                ),
            )
        )

        write_satellite_manifest_from_database(
            context=context,
            observation_id=(
                observation_id
            ),
        )

        print(
            "No usable Landsat thermal pixels; "
            "scene recorded as handled."
        )

        return

    observation_id = (
        save_satellite_observation(
            field_id=field_id,
            observed_on=(
                observed_on
            ),
            scene_id=item.id,
            cloud_cover_percent=(
                scene_cloud_percent
            ),
            metadata_json={
                **base_metadata,
                "processing_status":
                    "metrics_processed",
                "field_cloud_cover_percent":
                    field_cloud_percent,
                "field_usable_pixel_percent":
                    result.valid_pixel_percent,
            },
            source=(
                "landsat-c2-l2"
            ),
        )
    )

    raster_uris = (
        publish_metric_rasters(
            context=context,
            observed_on=(
                observed_on
            ),
            observation_id=(
                observation_id
            ),
            results=[
                result
            ],
        )
    )

    save_satellite_metrics(
        observation_id=(
            observation_id
        ),
        results=[
            result
        ],
        raster_uris=(
            raster_uris
        ),
    )

    try:
        anomaly = (
            detect_metric_anomalies(
                metric_type="lst_c",
                raster_path=(
                    result.raster_path
                ),
                field_geometry=(
                    geometry
                ),
            )
        )

        replace_satellite_anomalies(
            observation_id=(
                observation_id
            ),
            metric_type="lst_c",
            zones=(
                anomaly.zones
            ),
            analysis_json=(
                anomaly.analysis
            ),
        )

    except Exception as error:
        replace_satellite_anomalies(
            observation_id=(
                observation_id
            ),
            metric_type="lst_c",
            zones=[],
            analysis_json={
                "status":
                    "failed",
                "method":
                    "robust_mad_metric_v1",
                "metric_type":
                    "lst_c",
                "error_type":
                    type(error).__name__,
                "error_message":
                    str(error),
                "zone_count":
                    0,
            },
        )

        raise

    write_satellite_manifest_from_database(
        context=context,
        observation_id=(
            observation_id
        ),
    )

    print(
        "Landsat LST saved: "
        f"median {result.median:.1f} °C, "
        f"{result.valid_pixel_percent:.1f}% valid."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Landsat Collection 2 "
            "land-surface temperature for one field."
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
        "--max-scene-cloud",
        type=float,
        default=60.0,
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
        "Searching Landsat LST..."
    )

    items = search_landsat_l2(
        geometry=geometry,
        start_date=start_date,
        end_date=end_date,
        limit=args.limit,
    )

    print(
        f"Found {len(items)} thermal scenes."
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
                    LANDSAT_METRIC_TYPES
                ),
            )
        ):
            print(
                "Skipping already-ingested "
                f"thermal scene: {item.id}"
            )

            continue

        print()
        print(
            "=================================="
        )
        print(
            f"Thermal scene: {item.id}"
        )
        print(
            f"Date: {item.datetime.date()}"
        )

        with tempfile.TemporaryDirectory(
            prefix=(
                f"farm-lst-"
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
                    max_scene_cloud=(
                        args.max_scene_cloud
                    ),
                )

            except Exception as error:
                failed_scenes += 1

                print(
                    "FAILED thermal scene: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

    if failed_scenes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
