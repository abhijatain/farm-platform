from __future__ import annotations

import argparse
from datetime import date
from uuid import UUID

from satellite_worker.anomaly import detect_metric_anomalies
from satellite_worker.anomaly_rules import METRIC_ANOMALY_RULES
from satellite_worker.config import settings
from satellite_worker.db import (
    get_field_geometry,
    replace_satellite_anomalies,
    save_satellite_metrics,
    save_satellite_observation,
)
from satellite_worker.sentinel2.processor import process_metrics
from satellite_worker.stac import search_sentinel2

METRIC_TYPES = (
    "ndvi",
    "ndre",
    "ndmi",
    "gndvi",
    "evi2",
    "ndwi",
    "savi",
    "msavi",
    "bsi",
    "ndti",
    "ccci",
    "reci",
    "mcari",
)


MINIMUM_ANOMALY_VALID_PERCENT = 80.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Sentinel-2 field metrics "
            "and metric-aware anomaly zones "
            "for one farm field."
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
        help=("Maximum number of scenes. " "Use 0 for all matching scenes."),
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

        output_directory = (
            settings.satellite_output_dir / str(field_id) / observed_on.isoformat()
        )

        print()
        print("==================================")

        print(f"Scene: {item.id}")

        print(f"Date:  {observed_on}")

        try:
            # -------------------------------------------------
            # Generate all configured Sentinel-2 metric COGs.
            # -------------------------------------------------

            results = process_metrics(
                item=item,
                field_geometry=geometry,
                output_directory=(output_directory),
                metric_types=(METRIC_TYPES),
            )

            ndvi_result = next(
                (result for result in results if result.metric_type == "ndvi"),
                None,
            )

            if ndvi_result is None:
                raise RuntimeError("Generic metric processor " "did not produce NDVI.")

            cloud_cover = item.properties.get("eo:cloud_cover")

            metadata_json = {
                "processing_version": ("sentinel2-metrics-v1"),
                "stac_item_id": (item.id),
                "stac_collection": (item.collection_id),
                "datetime": (item.datetime.isoformat()),
                "platform": (item.properties.get("platform")),
                "constellation": (item.properties.get("constellation")),
                "processing_baseline": (
                    item.properties.get("s2:" "processing_baseline")
                ),
                "boa_offset_applied": (
                    item.properties.get("earthsearch:" "boa_offset_applied")
                ),
                "generated_metrics": [result.metric_type for result in results],
                "metric_formula_versions": {
                    result.metric_type: result.formula_version for result in results
                },
            }

            ndvi_raster_uri = ndvi_result.raster_path.resolve().as_uri()

            # -------------------------------------------------
            # Legacy observation columns.
            #
            # Keep these populated because the existing API
            # still exposes them and they remain useful for
            # backward compatibility.
            # -------------------------------------------------

            observation_id = save_satellite_observation(
                field_id=field_id,
                observed_on=(observed_on),
                scene_id=item.id,
                cloud_cover_percent=(
                    float(cloud_cover) if cloud_cover is not None else None
                ),
                valid_pixel_percent=(ndvi_result.valid_pixel_percent),
                ndvi_mean=(ndvi_result.mean),
                ndvi_median=(ndvi_result.median),
                ndvi_min=(ndvi_result.minimum),
                ndvi_max=(ndvi_result.maximum),
                ndvi_std=(ndvi_result.std),
                ndvi_raster_uri=(ndvi_raster_uri),
                resolution_m=(ndvi_result.output_resolution_m),
                pixel_count=(ndvi_result.pixel_count),
                valid_pixel_count=(ndvi_result.valid_pixel_count),
                metadata_json=(metadata_json),
            )

            # -------------------------------------------------
            # Generic metric records.
            # -------------------------------------------------

            save_satellite_metrics(
                observation_id=(observation_id),
                results=results,
            )

            # -------------------------------------------------
            # 8H metric-aware spatial anomaly detection.
            #
            # Each metric is analysed independently against the
            # distribution of pixels inside this field for this
            # observation.
            #
            # Important:
            # - NDVI/NDMI/etc may look for LOW anomalies.
            # - BSI may look for HIGH anomalies.
            # - NDWI/NDTI may be TWO-SIDED.
            # - No agronomic diagnosis is made here.
            # -------------------------------------------------

            print()
            print("Metric anomaly analysis:")

            total_anomaly_zones = 0

            for metric_result in results:
                metric_type = metric_result.metric_type.strip().lower()

                rule = METRIC_ANOMALY_RULES.get(metric_type)

                if rule is None:
                    print(
                        "  "
                        f"{metric_type.upper()}: "
                        "no anomaly rule configured; "
                        "skipped."
                    )

                    continue

                valid_percent = float(metric_result.valid_pixel_percent)

                if valid_percent < MINIMUM_ANOMALY_VALID_PERCENT:
                    analysis_json = {
                        "status": ("skipped_low_" "valid_coverage"),
                        "method": ("robust_mad_metric_v1"),
                        "metric_type": (metric_type),
                        "metric_label": (rule.label),
                        "direction": (rule.direction),
                        "valid_pixel_percent": (valid_percent),
                        "minimum_required_percent": (MINIMUM_ANOMALY_VALID_PERCENT),
                        "zone_count": 0,
                    }

                    replace_satellite_anomalies(
                        observation_id=(observation_id),
                        field_id=(field_id),
                        metric_type=(metric_type),
                        zones=[],
                        analysis_json=(analysis_json),
                    )

                    print(
                        "  "
                        f"{metric_type.upper()}: "
                        "skipped, only "
                        f"{valid_percent:.1f}% "
                        "valid pixels."
                    )

                    continue

                try:
                    anomaly_result = detect_metric_anomalies(
                        metric_type=(metric_type),
                        raster_path=(metric_result.raster_path),
                        field_geometry=(geometry),
                    )

                    replace_satellite_anomalies(
                        observation_id=(observation_id),
                        field_id=(field_id),
                        metric_type=(metric_type),
                        zones=(anomaly_result.zones),
                        analysis_json=(anomaly_result.analysis),
                    )

                    zone_count = len(anomaly_result.zones)

                    total_anomaly_zones += zone_count

                    print(
                        "  "
                        f"{metric_type.upper()}: "
                        f"{zone_count} zone" + ("" if zone_count == 1 else "s")
                    )

                    for zone in anomaly_result.zones:
                        print(
                            "    "
                            f"Zone "
                            f"{zone.zone_index}: "
                            f"{zone.anomaly_type}, "
                            f"{zone.severity}, "
                            f"{zone.area_acres:.3f} "
                            "acre, "
                            f"mean "
                            f"{zone.zone_mean_value:.3f}, "
                            f"field median "
                            f"{zone.field_median_value:.3f}"
                        )

                except Exception as error:
                    # Do not let one metric prevent the other
                    # metrics or the scene itself from being
                    # saved.
                    print(
                        "  "
                        f"{metric_type.upper()}: "
                        "anomaly detection failed: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

            print()
            print("Total anomaly zones " f"across metrics: " f"{total_anomaly_zones}")

            # -------------------------------------------------
            # Scene summary.
            # -------------------------------------------------

            print()
            print("Observation: " f"{observation_id}")

            print(
                "Metrics saved: "
                + ", ".join(result.metric_type.upper() for result in results)
            )

            print("NDVI raster: " f"{ndvi_result.raster_path}")

            print("Resolution: " f"{ndvi_result.output_resolution_m:.1f} m")

            print("Field pixels: " f"{ndvi_result.pixel_count}")

            print("Valid pixels: " f"{ndvi_result.valid_pixel_count}")

            print("Valid: " f"{ndvi_result.valid_pixel_percent:.1f}%")

            print("NDVI mean: " f"{ndvi_result.mean:.3f}")

            print("NDVI median: " f"{ndvi_result.median:.3f}")

            print(
                "NDVI range: "
                f"{ndvi_result.minimum:.3f}"
                " → "
                f"{ndvi_result.maximum:.3f}"
            )

        except Exception as error:
            print("FAILED: " f"{type(error).__name__}: " f"{error}")


if __name__ == "__main__":
    main()
