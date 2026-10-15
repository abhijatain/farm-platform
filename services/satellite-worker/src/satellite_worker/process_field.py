"""Process Sentinel-2 scenes, masked index rasters and anomaly zones."""

from __future__ import annotations

import argparse
import tempfile
from datetime import date
from pathlib import Path
from uuid import UUID

from satellite_worker.anomaly import (
    detect_metric_anomalies,
)
from satellite_worker.anomaly_rules import (
    METRIC_ANOMALY_RULES,
)
from satellite_worker.persistence.scenes import (
    replace_satellite_anomalies,
    satellite_scene_is_complete_for_automatic_ingestion,
    save_satellite_metrics,
    save_satellite_observation,
)
from satellite_worker.raster_storage import (
    publish_metric_rasters,
)
from satellite_worker.sentinel2.processor import (
    process_metrics,
)
from satellite_worker.stac import (
    search_sentinel2,
)
from satellite_worker.storage_context import (
    get_field_storage_context,
)
from satellite_worker.storage_manifests import (
    write_satellite_manifest_from_database,
)


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
            "Generate Sentinel-2 metrics and "
            "metric-aware anomaly zones for one field."
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
        help=(
            "Maximum number of scenes. "
            "Use 0 for all matching scenes."
        ),
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Skip scenes already complete for automatic ingestion. "
            "Legacy observations with existing metrics are always preserved."
        ),
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
        "Searching Sentinel-2..."
    )

    items = search_sentinel2(
        geometry=geometry,
        start_date=start_date,
        end_date=end_date,
        max_scene_cloud=(
            args.max_scene_cloud
        ),
        limit=args.limit,
        include_cloudy=True,
    )

    print(
        f"Found {len(items)} scenes."
    )

    failed_scenes = 0

    for item in items:
        if item.datetime is None:
            print(
                f"Skipping {item.id}: "
                "missing datetime."
            )

            continue

        observed_on = (
            item.datetime.date()
        )

        cloud_cover = (
            item.properties.get(
                "eo:cloud_cover"
            )
        )

        cloud_cover_percent = (
            float(
                cloud_cover
            )
            if cloud_cover
            is not None
            else None
        )

        observation_metadata = {
            "processing_version":
                "sentinel2-metrics-v2",
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
            "processing_baseline":
                item.properties.get(
                    "s2:processing_baseline"
                ),
            "boa_offset_applied":
                item.properties.get(
                    "earthsearch:"
                    "boa_offset_applied"
                ),
        }

        if (
            args.skip_existing
            and satellite_scene_is_complete_for_automatic_ingestion(
                field_id=field_id,
                scene_id=item.id,
                expected_metric_count=len(
                    METRIC_TYPES
                ),
            )
        ):
            print()
            print(
                "Skipping already-ingested scene: "
                f"{item.id} ({observed_on})"
            )

            continue

        if (
            cloud_cover_percent
            is not None
            and cloud_cover_percent
            >= args.max_scene_cloud
        ):
            skipped_metadata = {
                **observation_metadata,
                "processing_status":
                    "skipped_scene_cloud_cover",
                "skip_reason":
                    "scene_cloud_cover_threshold",
                "scene_cloud_cover_percent":
                    cloud_cover_percent,
                "scene_cloud_threshold_percent":
                    float(
                        args.max_scene_cloud
                    ),
            }

            observation_id = (
                save_satellite_observation(
                    field_id=field_id,
                    observed_on=(
                        observed_on
                    ),
                    scene_id=item.id,
                    cloud_cover_percent=(
                        cloud_cover_percent
                    ),
                    metadata_json=(
                        skipped_metadata
                    ),
                )
            )

            write_satellite_manifest_from_database(
                context=context,
                observation_id=(
                    observation_id
                ),
            )

            print()
            print(
                "Skipping cloudy scene: "
                f"{cloud_cover_percent:.1f}% "
                "scene cloud cover "
                f"(threshold {args.max_scene_cloud:.1f}%)."
            )

            continue

        print()
        print(
            "=================================="
        )
        print(
            f"Scene: {item.id}"
        )
        print(
            f"Date:  {observed_on}"
        )

        # COGs are generated only in an ephemeral working directory.
        # Nothing under services/satellite-worker/data is needed anymore.
        with tempfile.TemporaryDirectory(
            prefix=(
                f"farm-s2-"
                f"{field_id}-"
                f"{observed_on}-"
            )
        ) as temporary:
            output_directory = Path(
                temporary
            )

            try:
                processing = process_metrics(
                    item=item,
                    field_geometry=(
                        geometry
                    ),
                    output_directory=(
                        output_directory
                    ),
                    metric_types=(
                        METRIC_TYPES
                    ),
                )

                results = (
                    processing.metrics
                )

                coverage = (
                    processing.coverage
                )

                if not results:
                    skipped_metadata = {
                        **observation_metadata,
                        "processing_status":
                            "skipped_no_usable_pixels",
                        "skip_reason":
                            "no_usable_field_pixels_after_masks",
                        "scene_cloud_cover_percent":
                            cloud_cover_percent,
                        "field_cloud_cover_percent":
                            coverage.cloud_cover_percent,
                        "field_usable_pixel_percent":
                            coverage.usable_pixel_percent,
                        "field_excluded_pixel_percent":
                            coverage.excluded_pixel_percent,
                        "field_pixel_count":
                            coverage.pixel_count,
                    }

                    observation_id = (
                        save_satellite_observation(
                            field_id=field_id,
                            observed_on=(
                                observed_on
                            ),
                            scene_id=item.id,
                            cloud_cover_percent=(
                                cloud_cover_percent
                            ),
                            metadata_json=(
                                skipped_metadata
                            ),
                        )
                    )

                    write_satellite_manifest_from_database(
                        context=context,
                        observation_id=(
                            observation_id
                        ),
                    )

                    print()
                    print(
                        "Skipping unusable scene: "
                        f"{coverage.cloud_cover_percent:.1f}% "
                        "of field is cloud/shadow; "
                        f"{coverage.usable_pixel_percent:.1f}% "
                        "of field remains usable."
                    )

                    continue

                observation_metadata = {
                    **observation_metadata,
                    "processing_status":
                        "metrics_processed",
                    "scene_cloud_cover_percent":
                        cloud_cover_percent,
                    "field_cloud_cover_percent":
                        coverage.cloud_cover_percent,
                    "field_usable_pixel_percent":
                        coverage.usable_pixel_percent,
                    "field_excluded_pixel_percent":
                        coverage.excluded_pixel_percent,
                    "field_pixel_count":
                        coverage.pixel_count,
                }

                # Observation is scene-level only.
                observation_id = (
                    save_satellite_observation(
                        field_id=(
                            field_id
                        ),
                        observed_on=(
                            observed_on
                        ),
                        scene_id=(
                            item.id
                        ),
                        cloud_cover_percent=(
                            cloud_cover_percent
                        ),
                        metadata_json=(
                            observation_metadata
                        ),
                    )
                )

                print()
                print(
                    "Publishing metric COGs..."
                )

                # Upload directly from the temporary work directory and
                # obtain final canonical gs:// URIs.
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

                # PostgreSQL sees only permanent GCS URIs. It never points
                # at a temporary local file.
                save_satellite_metrics(
                    observation_id=(
                        observation_id
                    ),
                    results=results,
                    raster_uris=(
                        raster_uris
                    ),
                )

                print()
                print(
                    "Metric anomaly analysis:"
                )

                total_anomaly_zones = 0
                anomaly_failures: list[str] = []

                for metric_result in results:
                    metric_type = (
                        metric_result
                        .metric_type
                        .strip()
                        .lower()
                    )

                    rule = (
                        METRIC_ANOMALY_RULES
                        .get(
                            metric_type
                        )
                    )

                    if rule is None:
                        print(
                            "  "
                            f"{metric_type.upper()}: "
                            "no anomaly rule; skipped."
                        )

                        continue

                    valid_percent = float(
                        metric_result
                        .valid_pixel_percent
                    )

                    if (
                        valid_percent
                        < MINIMUM_ANOMALY_VALID_PERCENT
                    ):
                        replace_satellite_anomalies(
                            observation_id=(
                                observation_id
                            ),
                            metric_type=(
                                metric_type
                            ),
                            zones=[],
                            analysis_json={
                                "status":
                                    "skipped_low_"
                                    "valid_coverage",
                                "method":
                                    "robust_mad_metric_v1",
                                "metric_type":
                                    metric_type,
                                "metric_label":
                                    rule.label,
                                "direction":
                                    rule.direction,
                                "valid_pixel_percent":
                                    valid_percent,
                                "minimum_required_percent":
                                    MINIMUM_ANOMALY_VALID_PERCENT,
                                "zone_count":
                                    0,
                            },
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
                        anomaly_result = (
                            detect_metric_anomalies(
                                metric_type=(
                                    metric_type
                                ),
                                raster_path=(
                                    metric_result
                                    .raster_path
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
                            metric_type=(
                                metric_type
                            ),
                            zones=(
                                anomaly_result
                                .zones
                            ),
                            analysis_json=(
                                anomaly_result
                                .analysis
                            ),
                        )

                        zone_count = len(
                            anomaly_result
                            .zones
                        )

                        total_anomaly_zones += (
                            zone_count
                        )

                        print(
                            "  "
                            f"{metric_type.upper()}: "
                            f"{zone_count} zone"
                            + (
                                ""
                                if zone_count == 1
                                else "s"
                            )
                        )

                    except Exception as error:
                        # Never keep polygons from an older run attached to a
                        # newly-published metric raster.
                        replace_satellite_anomalies(
                            observation_id=(
                                observation_id
                            ),
                            metric_type=(
                                metric_type
                            ),
                            zones=[],
                            analysis_json={
                                "status": "failed",
                                "method": "robust_mad_metric_v1",
                                "metric_type": metric_type,
                                "metric_label": rule.label,
                                "direction": rule.direction,
                                "valid_pixel_percent": valid_percent,
                                "zone_count": 0,
                                "error_type": type(error).__name__,
                                "error_message": str(error),
                            },
                        )

                        anomaly_failures.append(
                            metric_type
                        )

                        print(
                            "  "
                            f"{metric_type.upper()}: "
                            "anomaly detection failed: "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )

                # Recovery manifest is generated from canonical DB rows and
                # permanent GCS object URIs.
                write_satellite_manifest_from_database(
                    context=context,
                    observation_id=(
                        observation_id
                    ),
                )

                if anomaly_failures:
                    raise RuntimeError(
                        "Anomaly analysis failed for: "
                        + ", ".join(
                            metric.upper()
                            for metric in anomaly_failures
                        )
                    )

                print()
                print(
                    "Observation: "
                    f"{observation_id}"
                )

                print(
                    "Metrics saved: "
                    + ", ".join(
                        result
                        .metric_type
                        .upper()
                        for result
                        in results
                    )
                )

                print(
                    "Total anomaly zones: "
                    f"{total_anomaly_zones}"
                )

            except Exception as error:
                failed_scenes += 1

                print(
                    "FAILED: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

    if failed_scenes:
        print()
        print(
            "Processing completed with "
            f"{failed_scenes} failed scene"
            + ("" if failed_scenes == 1 else "s")
            + "."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
