from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path
from uuid import UUID

from satellite_worker.anomaly import detect_ndvi_anomalies
from satellite_worker.config import settings
from satellite_worker.db import (
    get_field_geometry,
    replace_satellite_anomalies,
    save_satellite_observation,
)
from satellite_worker.ndvi import calculate_ndvi
from satellite_worker.stac import (
    NIR_ASSET_NAMES,
    RED_ASSET_NAMES,
    SCL_ASSET_NAMES,
    get_asset,
    search_sentinel2,
)


def safe_filename(
    value: str,
) -> str:

    return re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        value,
    )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Generate per-pixel Sentinel-2 " "NDVI rasters for one farm field."
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

    args = parser.parse_args()

    field_id = UUID(args.field_id)

    start_date = date.fromisoformat(args.start)

    end_date = date.fromisoformat(args.end)

    geometry = get_field_geometry(field_id)

    print("Searching Sentinel-2...")

    items = search_sentinel2(
        geometry=geometry,
        start_date=start_date,
        end_date=end_date,
        max_scene_cloud=(args.max_scene_cloud),
        limit=args.limit,
    )

    print(f"Found {len(items)} scenes.")

    if not items:
        return

    for item in items:

        if item.datetime is None:
            print(f"Skipping {item.id}: " "missing datetime.")

            continue

        observed_on = item.datetime.date()

        scene_name = safe_filename(item.id)

        output_path = (
            settings.satellite_output_dir
            / str(field_id)
            / observed_on.isoformat()
            / f"{scene_name}_ndvi.tif"
        )

        print()
        print("==================================")

        print(f"Scene: {item.id}")

        print(f"Date:  {observed_on}")

        try:

            result = calculate_ndvi(
                item=item,
                field_geometry=(geometry),
                output_path=(output_path),
            )

            cloud_cover = item.properties.get("eo:cloud_cover")

            red_asset = get_asset(
                item,
                RED_ASSET_NAMES,
            )

            nir_asset = get_asset(
                item,
                NIR_ASSET_NAMES,
            )

            scl_asset = get_asset(
                item,
                SCL_ASSET_NAMES,
            )

            metadata_json = {
                "processing_version": "ndvi-v1",
                "stac_item_id": item.id,
                "stac_collection": item.collection_id,
                "datetime": item.datetime.isoformat(),
                "platform": item.properties.get("platform"),
                "constellation": item.properties.get("constellation"),
                "red_asset": red_asset.href,
                "nir_asset": nir_asset.href,
                "scl_asset": scl_asset.href,
            }

            raster_uri = result.raster_path.resolve().as_uri()

            observation_id = save_satellite_observation(
                field_id=(field_id),
                observed_on=(observed_on),
                scene_id=(item.id),
                cloud_cover_percent=(
                    float(cloud_cover) if cloud_cover is not None else None
                ),
                valid_pixel_percent=(result.valid_pixel_percent),
                ndvi_mean=(result.mean),
                ndvi_median=(result.median),
                ndvi_min=(result.minimum),
                ndvi_max=(result.maximum),
                ndvi_std=(result.std),
                ndvi_raster_uri=(raster_uri),
                resolution_m=(result.resolution_m),
                pixel_count=(result.pixel_count),
                valid_pixel_count=(result.valid_pixel_count),
                metadata_json=(metadata_json),
            )
            if result.valid_pixel_percent >= 80.0:

                try:

                    anomaly_result = detect_ndvi_anomalies(
                        raster_path=result.raster_path,
                        field_geometry=geometry,
                    )

                    replace_satellite_anomalies(
                        observation_id=observation_id,
                        field_id=field_id,
                        zones=anomaly_result.zones,
                        analysis_json=anomaly_result.analysis,
                    )

                    print("Anomaly zones: " f"{len(anomaly_result.zones)}")

                    for zone in anomaly_result.zones:

                        print(
                            "  "
                            f"Zone {zone.zone_index}: "
                            f"{zone.severity}, "
                            f"{zone.area_acres:.3f} acre, "
                            f"NDVI {zone.zone_mean_value:.3f}, "
                            f"field {zone.field_median_value:.3f}"
                        )

                except Exception as error:

                    print(
                        "Anomaly detection failed: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

            else:

                replace_satellite_anomalies(
                    observation_id=observation_id,
                    field_id=field_id,
                    zones=[],
                    analysis_json={
                        "status": "skipped_low_valid_coverage",
                        "method": "robust_mad_v1",
                        "valid_pixel_percent": result.valid_pixel_percent,
                        "minimum_required_percent": 80.0,
                        "zone_count": 0,
                    },
                )

                print(
                    "Anomaly detection skipped: "
                    f"only "
                    f"{result.valid_pixel_percent:.1f}% "
                    "valid pixels."
                )

            print(f"Observation: " f"{observation_id}")

            print(f"Raster: " f"{result.raster_path}")

            print(f"Resolution: " f"{result.resolution_m:.1f} m")

            print(f"Field pixels: " f"{result.pixel_count}")

            print(f"Valid pixels: " f"{result.valid_pixel_count}")

            print(f"Valid: " f"{result.valid_pixel_percent:.1f}%")

            print(f"NDVI mean: " f"{result.mean:.3f}")

            print(f"NDVI median: " f"{result.median:.3f}")

            print(f"NDVI range: " f"{result.minimum:.3f}" " → " f"{result.maximum:.3f}")

        except Exception as error:

            print(f"FAILED: " f"{type(error).__name__}: " f"{error}")


if __name__ == "__main__":
    main()
