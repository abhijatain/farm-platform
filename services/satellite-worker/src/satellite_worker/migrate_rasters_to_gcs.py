
from __future__ import annotations

import argparse
from uuid import UUID

from satellite_worker.db import (
    list_satellite_metric_rasters_for_backfill,
)
from satellite_worker.raster_storage import (
    local_raster_uri_to_path,
    update_satellite_raster_uris,
    upload_existing_metric_raster,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Move already-generated local "
            "satellite metric COGs to GCS."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Maximum metric rows to migrate. "
            "Use 0 for all."
        ),
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
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--delete-local",
        action="store_true",
        help=(
            "Delete each local COG only "
            "after upload verification and "
            "DB update succeed."
        ),
    )

    args = parser.parse_args()

    rows = (
        list_satellite_metric_rasters_for_backfill(
            field_id=(
                args.field_id
            ),
            observation_id=(
                args.observation_id
            ),
            limit=args.limit,
            only_missing=False,
        )
    )

    local_rows = [
        row
        for row in rows
        if str(
            row["raster_uri"]
        ).startswith(
            (
                "file://",
                "/",
                ".",
            )
        )
    ]

    print(
        "Local metric COGs: "
        f"{len(local_rows)}"
    )

    if not local_rows:
        return

    if args.dry_run:
        for row in local_rows:
            print(
                f"{row['observed_on']}  "
                f"{row['field_name']}  "
                f"{str(row['metric_type']).upper()}  "
                f"{row['raster_uri']}"
            )

        print()
        print(
            "Dry run only. "
            "Nothing uploaded or changed."
        )

        return

    completed = 0
    failed = 0

    for index, row in enumerate(
        local_rows,
        start=1,
    ):
        field_id = UUID(
            str(
                row["field_id"]
            )
        )

        observation_id = UUID(
            str(
                row[
                    "observation_id"
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

        raster_uri = str(
            row[
                "raster_uri"
            ]
        )

        print(
            f"[{index}/{len(local_rows)}] "
            f"{row['field_name']} "
            f"{row['observed_on']} "
            f"{metric_type.upper()}"
        )

        try:
            source_path = (
                local_raster_uri_to_path(
                    raster_uri
                )
            )

            if not source_path.is_file():
                raise FileNotFoundError(
                    "Local COG not found: "
                    f"{source_path}"
                )

            gcs_uri = (
                upload_existing_metric_raster(
                    field_id=(
                        field_id
                    ),
                    observation_id=(
                        observation_id
                    ),
                    metric_type=(
                        metric_type
                    ),
                    source_path=(
                        source_path
                    ),
                )
            )

            update_satellite_raster_uris(
                observation_id=(
                    observation_id
                ),
                raster_uris={
                    metric_type:
                        gcs_uri
                },
            )

            if args.delete_local:
                source_path.unlink(
                    missing_ok=True
                )

            completed += 1

            print(
                f"  → {gcs_uri}"
            )

        except Exception as error:
            failed += 1

            print(
                "  FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    print()
    print(
        "Migration complete"
    )

    print(
        f"Completed: {completed}"
    )

    print(
        f"Failed:    {failed}"
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
