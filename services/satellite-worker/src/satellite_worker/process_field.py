
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
from satellite_worker.db import (
    replace_satellite_anomalies,
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
    )

    print(
        f"Found {len(items)} scenes."
    )

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
                results = process_metrics(
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

                if not results:
                    raise RuntimeError(
                        "Metric processor produced "
                        "no results."
                    )

                cloud_cover = (
                    item.properties.get(
                        "eo:cloud_cover"
                    )
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
                            float(
                                cloud_cover
                            )
                            if cloud_cover
                            is not None
                            else None
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
                print(
                    "FAILED: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )


if __name__ == "__main__":
    main()
