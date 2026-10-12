from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import UUID

from satellite_worker.anomaly import detect_metric_anomalies
from satellite_worker.anomaly_rules import METRIC_ANOMALY_RULES
from satellite_worker.db import (
    get_field_geometry,
    list_satellite_metric_rasters_for_backfill,
    replace_satellite_anomalies,
)

DEFAULT_MINIMUM_VALID_PERCENT = 80.0


def raster_uri_to_path(
    raster_uri: str,
) -> Path:
    """Convert a stored local raster URI into a filesystem Path."""

    value = raster_uri.strip()

    if not value:
        raise ValueError("Raster URI is empty.")

    parsed = urlparse(value)

    if parsed.scheme == "":
        return Path(unquote(value))

    if parsed.scheme != "file":
        raise ValueError(
            "Backfill currently supports local "
            "file:// raster URIs only. "
            f"Received: {raster_uri}"
        )

    if parsed.netloc not in (
        "",
        "localhost",
    ):
        raise ValueError("Unsupported file URI host: " f"{parsed.netloc}")

    path_value = unquote(parsed.path)

    # file:///C:/... needs the leading slash removed
    # when this worker is ever run directly on Windows.
    if (
        os.name == "nt"
        and len(path_value) >= 3
        and path_value[0] == "/"
        and path_value[2] == ":"
    ):
        path_value = path_value[1:]

    return Path(path_value)


def parse_optional_date(
    value: str | None,
) -> date | None:
    if value is None:
        return None

    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill metric-aware anomaly zones from "
            "already-generated satellite metric COGs."
        )
    )

    parser.add_argument(
        "--field-id",
        type=UUID,
        default=None,
        help=("Optional field UUID. " "Omit to include all fields."),
    )

    parser.add_argument(
        "--observation-id",
        type=UUID,
        default=None,
        help=(
            "Optional satellite observation UUID. " "Useful for a one-observation test."
        ),
    )

    parser.add_argument(
        "--metric",
        action="append",
        choices=tuple(METRIC_ANOMALY_RULES.keys()),
        default=None,
        help=(
            "Metric to process. Repeat this flag for "
            "multiple metrics. Omit for all configured metrics."
        ),
    )

    parser.add_argument(
        "--start",
        default=None,
        help=("Optional first observation date " "in YYYY-MM-DD format."),
    )

    parser.add_argument(
        "--end",
        default=None,
        help=("Optional last observation date " "in YYYY-MM-DD format."),
    )

    parser.add_argument(
        "--minimum-valid-percent",
        type=float,
        default=(DEFAULT_MINIMUM_VALID_PERCENT),
        help=("Skip anomaly detection below this " "valid-pixel percentage."),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=("Maximum metric rows to process. " "Use 0 for all matching rows."),
    )

    parser.add_argument(
        "--only-missing",
        action="store_true",
        help=(
            "Process only observation/metric pairs "
            "without anomaly_detection metadata."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "List matching rows without running "
            "detection or writing to the database."
        ),
    )

    args = parser.parse_args()

    start_date = parse_optional_date(args.start)

    end_date = parse_optional_date(args.end)

    if start_date is not None and end_date is not None and start_date > end_date:
        parser.error("--start cannot be after --end.")

    if not (0.0 <= args.minimum_valid_percent <= 100.0):
        parser.error("--minimum-valid-percent must be " "between 0 and 100.")

    if args.limit < 0:
        parser.error("--limit cannot be negative.")

    metric_types = (
        tuple(args.metric) if args.metric else tuple(METRIC_ANOMALY_RULES.keys())
    )

    rows = list_satellite_metric_rasters_for_backfill(
        field_id=args.field_id,
        observation_id=(args.observation_id),
        metric_types=(metric_types),
        start_date=(start_date),
        end_date=(end_date),
        limit=args.limit,
        only_missing=(args.only_missing),
    )

    print("Metric anomaly backfill")

    print("Matching metric rows: " f"{len(rows)}")

    if not rows:
        return

    if args.dry_run:
        for row in rows:
            print(
                f"{row['observed_on']}  "
                f"{row['field_name']}  "
                f"{row['metric_type'].upper()}  "
                f"{row['observation_id']}"
            )

        print()
        print("Dry run only. " "No anomaly detection was executed.")

        return

    geometry_cache: dict[
        UUID,
        dict,
    ] = {}

    completed = 0
    skipped_low_coverage = 0
    failed = 0
    total_zones = 0

    current_observation_id: UUID | None = None

    for row in rows:
        observation_id = UUID(str(row["observation_id"]))

        field_id = UUID(str(row["field_id"]))

        metric_type = str(row["metric_type"]).strip().lower()

        observed_on = row["observed_on"]

        field_name = row["field_name"] or str(field_id)

        if current_observation_id != observation_id:
            current_observation_id = observation_id

            print()
            print("==================================")
            print(f"Observation: {observation_id}")
            print(f"Field:       {field_name}")
            print(f"Date:        {observed_on}")

        rule = METRIC_ANOMALY_RULES.get(metric_type)

        if rule is None:
            print("  " f"{metric_type.upper()}: " "no anomaly rule; skipped.")

            continue

        valid_percent_raw = row["valid_pixel_percent"]

        valid_percent = (
            float(valid_percent_raw) if valid_percent_raw is not None else None
        )

        if valid_percent is not None and valid_percent < args.minimum_valid_percent:
            analysis_json = {
                "status": ("skipped_low_" "valid_coverage"),
                "method": ("robust_mad_metric_v1"),
                "metric_type": (metric_type),
                "metric_label": (rule.label),
                "direction": (rule.direction),
                "valid_pixel_percent": (valid_percent),
                "minimum_required_percent": (args.minimum_valid_percent),
                "zone_count": 0,
                "backfilled": True,
            }

            try:
                replace_satellite_anomalies(
                    observation_id=(observation_id),
                    field_id=(field_id),
                    metric_type=(metric_type),
                    zones=[],
                    analysis_json=(analysis_json),
                )

                skipped_low_coverage += 1

                print(
                    "  "
                    f"{metric_type.upper()}: "
                    "skipped, "
                    f"{valid_percent:.1f}% valid"
                )

            except Exception as error:
                failed += 1

                print(
                    "  "
                    f"{metric_type.upper()}: "
                    "FAILED saving low-coverage "
                    "status: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            continue

        try:
            raster_path = raster_uri_to_path(str(row["raster_uri"]))

            if not raster_path.is_file():
                raise FileNotFoundError("Metric raster not found: " f"{raster_path}")

            geometry = geometry_cache.get(field_id)

            if geometry is None:
                geometry = get_field_geometry(field_id)

                geometry_cache[field_id] = geometry

            anomaly_result = detect_metric_anomalies(
                metric_type=(metric_type),
                raster_path=(raster_path),
                field_geometry=(geometry),
            )

            analysis_json = dict(anomaly_result.analysis)

            analysis_json["backfilled"] = True

            replace_satellite_anomalies(
                observation_id=(observation_id),
                field_id=(field_id),
                metric_type=(metric_type),
                zones=(anomaly_result.zones),
                analysis_json=(analysis_json),
            )

            zone_count = len(anomaly_result.zones)

            completed += 1
            total_zones += zone_count

            print(
                "  "
                f"{metric_type.upper()}: "
                f"{zone_count} zone" + ("" if zone_count == 1 else "s")
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
    print("==================================")
    print("Backfill summary")
    print(f"Processed:            {completed}")
    print("Skipped low coverage: " f"{skipped_low_coverage}")
    print(f"Total zones:          {total_zones}")
    print(f"Failed:               {failed}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
