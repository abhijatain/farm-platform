"""Backfill older metric anomaly geometry without re-ingesting scenes."""

from __future__ import annotations

import argparse
from datetime import date
from uuid import UUID

from satellite_worker.anomaly import (
    detect_metric_anomalies,
)
from satellite_worker.anomaly_rules import (
    METRIC_ANOMALY_RULES,
)
from satellite_worker.db import (
    get_field_geometry,
    list_satellite_metric_rasters_for_backfill,
    replace_satellite_anomalies,
)
from satellite_worker.raster_storage import (
    materialize_metric_raster,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recalculate metric-aware anomaly zones "
            "from existing GCS metric COGs."
        )
    )

    parser.add_argument(
        "--field-id",
        type=UUID,
        default=None,
    )

    parser.add_argument(
        "--observation-id",
        type=UUID,
        default=None,
    )

    parser.add_argument(
        "--metric",
        dest="metrics",
        action="append",
        default=[],
        help=(
            "Metric to process. Repeat for multiple metrics. "
            "If omitted, all configured metrics are considered."
        ),
    )

    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
    )

    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
    )

    parser.add_argument(
        "--minimum-valid-percent",
        type=float,
        default=80.0,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="0 means no limit.",
    )

    parser.add_argument(
        "--only-missing",
        action="store_true",
        help=(
            "Only process metric rows without "
            "metadata_json.anomaly_analysis."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    if not (
        0.0
        <= args.minimum_valid_percent
        <= 100.0
    ):
        parser.error(
            "--minimum-valid-percent must be "
            "between 0 and 100."
        )

    if args.limit < 0:
        parser.error(
            "--limit must be 0 or greater."
        )

    return args


def main() -> None:
    args = parse_args()

    normalized_metrics = tuple(
        metric
        .strip()
        .lower()
        for metric in args.metrics
        if metric.strip()
    )

    rows = (
        list_satellite_metric_rasters_for_backfill(
            field_id=(
                args.field_id
            ),
            observation_id=(
                args.observation_id
            ),
            metric_types=(
                normalized_metrics
                or None
            ),
            start_date=(
                args.start
            ),
            end_date=(
                args.end
            ),
            limit=args.limit,
            only_missing=(
                args.only_missing
            ),
        )
    )

    print(
        "Metric rasters selected: "
        f"{len(rows)}"
    )

    if args.dry_run:
        for row in rows:
            print(
                f"{row['observed_on']}  "
                f"{row['field_name']}  "
                f"{str(row['metric_type']).upper()}  "
                f"{row['raster_uri']}"
            )

        print()
        print(
            "Dry run only. "
            "No anomaly rows changed."
        )

        return

    geometry_cache: dict[
        UUID,
        dict,
    ] = {}

    completed = 0
    skipped_low_coverage = 0
    skipped_no_rule = 0
    total_zones = 0
    failed = 0

    current_observation_id = None

    for row in rows:
        observation_id = UUID(
            str(
                row[
                    "observation_id"
                ]
            )
        )

        field_id = UUID(
            str(
                row[
                    "field_id"
                ]
            )
        )

        metric_type = (
            str(
                row[
                    "metric_type"
                ]
            )
            .strip()
            .lower()
        )

        if (
            current_observation_id
            != observation_id
        ):
            current_observation_id = (
                observation_id
            )

            print()
            print(
                "=================================="
            )
            print(
                "Observation: "
                f"{observation_id}"
            )
            print(
                "Field:       "
                f"{row['field_name']}"
            )
            print(
                "Date:        "
                f"{row['observed_on']}"
            )

        rule = (
            METRIC_ANOMALY_RULES
            .get(
                metric_type
            )
        )

        if rule is None:
            skipped_no_rule += 1

            print(
                "  "
                f"{metric_type.upper()}: "
                "no anomaly rule; skipped."
            )

            continue

        valid_raw = row[
            "valid_pixel_percent"
        ]

        valid_percent = (
            float(
                valid_raw
            )
            if valid_raw
            is not None
            else None
        )

        if (
            valid_percent
            is not None
            and valid_percent
            < args.minimum_valid_percent
        ):
            try:
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
                            args.minimum_valid_percent,
                        "zone_count":
                            0,
                        "backfilled":
                            True,
                    },
                )

                skipped_low_coverage += 1

                print(
                    "  "
                    f"{metric_type.upper()}: "
                    "skipped, "
                    f"{valid_percent:.1f}% valid."
                )

            except Exception as error:
                failed += 1

                print(
                    "  "
                    f"{metric_type.upper()}: "
                    "FAILED saving low-coverage status: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            continue

        try:
            geometry = (
                geometry_cache
                .get(
                    field_id
                )
            )

            if geometry is None:
                geometry = (
                    get_field_geometry(
                        field_id
                    )
                )

                geometry_cache[
                    field_id
                ] = geometry

            # Maintenance algorithms still work on a local rasterio path,
            # but the COG is downloaded only to an auto-deleted temp dir.
            with materialize_metric_raster(
                str(
                    row[
                        "raster_uri"
                    ]
                )
            ) as raster_path:
                anomaly_result = (
                    detect_metric_anomalies(
                        metric_type=(
                            metric_type
                        ),
                        raster_path=(
                            raster_path
                        ),
                        field_geometry=(
                            geometry
                        ),
                    )
                )

            analysis_json = dict(
                anomaly_result.analysis
            )

            analysis_json[
                "backfilled"
            ] = True

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
                    analysis_json
                ),
            )

            zone_count = len(
                anomaly_result.zones
            )

            completed += 1
            total_zones += zone_count

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
            failed += 1

            print(
                "  "
                f"{metric_type.upper()}: "
                "FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    print()
    print(
        "=================================="
    )
    print(
        "Backfill summary"
    )
    print(
        "Processed:            "
        f"{completed}"
    )
    print(
        "Skipped low coverage: "
        f"{skipped_low_coverage}"
    )
    print(
        "Skipped no rule:      "
        f"{skipped_no_rule}"
    )
    print(
        "Total zones:          "
        f"{total_zones}"
    )
    print(
        "Failed:               "
        f"{failed}"
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
