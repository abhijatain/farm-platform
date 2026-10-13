
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import text

from satellite_worker.db import engine
from satellite_worker.gcs_client import (
    gcs_bucket,
    gcs_client,
)
from satellite_worker.storage_context import (
    get_field_storage_context,
)
from satellite_worker.storage_layout import (
    STORAGE_LAYOUT_VERSION,
    media_prefix,
    satellite_metric_key,
)
from satellite_worker.storage_manifests import (
    write_media_manifest_from_database,
    write_satellite_manifest_from_database,
)


def _parse_gs_uri(
    uri: str,
) -> tuple[str, str]:
    parsed = urlparse(uri)

    if (
        parsed.scheme != "gs"
        or not parsed.netloc
    ):
        raise ValueError(
            f"Not a gs:// URI: {uri}"
        )

    return (
        parsed.netloc,
        parsed.path.lstrip("/"),
    )


def _copy_verified(
    *,
    source_bucket_name: str,
    source_key: str,
    destination_bucket_name: str,
    destination_key: str,
) -> None:
    if (
        source_bucket_name
        == destination_bucket_name
        and source_key
        == destination_key
    ):
        return

    client = gcs_client()

    source_bucket = client.bucket(
        source_bucket_name
    )

    destination_bucket = client.bucket(
        destination_bucket_name
    )

    source_blob = source_bucket.blob(
        source_key
    )

    if not source_blob.exists(
        client
    ):
        raise FileNotFoundError(
            "Missing GCS object: "
            f"gs://{source_bucket_name}/{source_key}"
        )

    source_blob.reload(
        client=client
    )

    copied = source_bucket.copy_blob(
        source_blob,
        destination_bucket,
        new_name=destination_key,
    )

    copied.reload(
        client=client
    )

    if int(
        source_blob.size or 0
    ) != int(
        copied.size or 0
    ):
        try:
            copied.delete(
                client=client
            )
        except Exception:
            pass

        raise RuntimeError(
            "GCS copy size mismatch."
        )


def _delete_old(
    *,
    old_bucket_name: str,
    old_key: str,
    new_bucket_name: str,
    new_key: str,
) -> None:
    if (
        old_bucket_name
        == new_bucket_name
        and old_key
        == new_key
    ):
        return

    try:
        gcs_client().bucket(
            old_bucket_name
        ).blob(
            old_key
        ).delete(
            client=gcs_client()
        )
    except Exception as error:
        print(
            "    warning: could not delete old object: "
            f"{error}"
        )


def _satellite_rows() -> list[dict]:
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(
                    """
                    SELECT
                        so.id AS observation_id,
                        so.field_id,
                        so.observed_on

                    FROM satellite_observations AS so

                    WHERE EXISTS (
                        SELECT 1
                        FROM satellite_metrics AS sm
                        WHERE
                            sm.satellite_observation_id = so.id
                        AND sm.raster_uri LIKE 'gs://%'
                    )

                    ORDER BY
                        so.observed_on,
                        so.id
                    """
                )
            ).mappings().all()
        ]


def _metric_rows(
    observation_id: UUID,
) -> list[dict]:
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(
                    """
                    SELECT
                        metric_type,
                        raster_uri

                    FROM satellite_metrics

                    WHERE
                        satellite_observation_id = :observation_id

                    AND raster_uri LIKE 'gs://%'

                    ORDER BY metric_type
                    """
                ),
                {
                    "observation_id":
                        observation_id,
                },
            ).mappings().all()
        ]


def _migrate_satellite(
    *,
    dry_run: bool,
    delete_old: bool,
    limit: int,
) -> tuple[int, int]:
    rows = _satellite_rows()

    if limit > 0:
        rows = rows[:limit]

    completed = 0
    failed = 0

    for index, row in enumerate(
        rows,
        start=1,
    ):
        observation_id = UUID(
            str(
                row["observation_id"]
            )
        )

        field_id = UUID(
            str(
                row["field_id"]
            )
        )

        observed_on = row[
            "observed_on"
        ]

        context = (
            get_field_storage_context(
                field_id
            )
        )

        metrics = _metric_rows(
            observation_id
        )

        print(
            f"[satellite {index}/{len(rows)}] "
            f"{context['farm_name']} / "
            f"{context['field_name']} / "
            f"{observed_on}"
        )

        if dry_run:
            for metric in metrics:
                new_key = (
                    satellite_metric_key(
                        context=context,
                        observed_on=observed_on,
                        observation_id=(
                            observation_id
                        ),
                        metric_type=(
                            metric[
                                "metric_type"
                            ]
                        ),
                    )
                )

                print(
                    "    "
                    f"{metric['metric_type'].upper()} "
                    f"→ gs://{gcs_bucket().name}/{new_key}"
                )

            continue

        copied: list[
            tuple[
                str,
                str,
                str,
                str,
            ]
        ] = []

        new_uris: dict[
            str,
            str,
        ] = {}

        try:
            for metric in metrics:
                metric_type = str(
                    metric["metric_type"]
                ).strip().lower()

                old_bucket, old_key = (
                    _parse_gs_uri(
                        str(
                            metric[
                                "raster_uri"
                            ]
                        )
                    )
                )

                new_key = (
                    satellite_metric_key(
                        context=context,
                        observed_on=observed_on,
                        observation_id=(
                            observation_id
                        ),
                        metric_type=(
                            metric_type
                        ),
                    )
                )

                _copy_verified(
                    source_bucket_name=(
                        old_bucket
                    ),
                    source_key=(
                        old_key
                    ),
                    destination_bucket_name=(
                        gcs_bucket().name
                    ),
                    destination_key=(
                        new_key
                    ),
                )

                copied.append(
                    (
                        old_bucket,
                        old_key,
                        gcs_bucket().name,
                        new_key,
                    )
                )

                new_uris[
                    metric_type
                ] = (
                    f"gs://{gcs_bucket().name}/{new_key}"
                )

            with engine.begin() as connection:
                for (
                    metric_type,
                    new_uri,
                ) in new_uris.items():
                    connection.execute(
                        text(
                            """
                            UPDATE satellite_metrics
                            SET
                                raster_uri = :raster_uri,
                                metadata_json =
                                    COALESCE(
                                        metadata_json,
                                        '{}'::jsonb
                                    )
                                    ||
                                    jsonb_build_object(
                                        'storage_layout_version',
                                        CAST(
                                            :layout_version
                                            AS integer
                                        )
                                    ),
                                updated_at = NOW()
                            WHERE
                                satellite_observation_id = :observation_id
                            AND metric_type = :metric_type
                            """
                        ),
                        {
                            "observation_id":
                                observation_id,
                            "metric_type":
                                metric_type,
                            "raster_uri":
                                new_uri,
                            "layout_version":
                                STORAGE_LAYOUT_VERSION,
                        },
                    )

                connection.execute(
                    text(
                        """
                        UPDATE satellite_observations
                        SET
                            ndvi_raster_uri =
                                COALESCE(
                                    :ndvi_uri,
                                    ndvi_raster_uri
                                ),
                            metadata_json =
                                COALESCE(
                                    metadata_json,
                                    '{}'::jsonb
                                )
                                ||
                                jsonb_build_object(
                                    'raster_storage',
                                    COALESCE(
                                        metadata_json
                                            -> 'raster_storage',
                                        '{}'::jsonb
                                    )
                                    ||
                                    jsonb_build_object(
                                        'layout_version',
                                        CAST(
                                            :layout_version
                                            AS integer
                                        )
                                    )
                                ),
                            updated_at = NOW()
                        WHERE id = :observation_id
                        """
                    ),
                    {
                        "observation_id":
                            observation_id,
                        "ndvi_uri":
                            new_uris.get(
                                "ndvi"
                            ),
                        "layout_version":
                            STORAGE_LAYOUT_VERSION,
                    },
                )

            write_satellite_manifest_from_database(
                context=context,
                observation_id=(
                    observation_id
                ),
            )

            if delete_old:
                for (
                    old_bucket,
                    old_key,
                    new_bucket,
                    new_key,
                ) in copied:
                    _delete_old(
                        old_bucket_name=(
                            old_bucket
                        ),
                        old_key=(
                            old_key
                        ),
                        new_bucket_name=(
                            new_bucket
                        ),
                        new_key=(
                            new_key
                        ),
                    )

            completed += 1

        except Exception as error:
            failed += 1

            print(
                "    FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    return completed, failed


def _media_rows() -> list[dict]:
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(
                    """
                    SELECT
                        ma.id AS media_id,
                        ma.field_id,
                        ma.bucket_name,
                        ma.object_key,
                        ma.thumbnail_object_key,
                        ma.original_filename,
                        ma.captured_at,
                        ma.created_at,
                        ma.metadata_json

                    FROM media_assets AS ma

                    WHERE
                        ma.storage_backend = 'gcs'

                    ORDER BY
                        ma.created_at,
                        ma.id
                    """
                )
            ).mappings().all()
        ]


def _media_storage_date(
    row: dict,
) -> date:
    metadata = (
        row["metadata_json"]
        or {}
    )

    raw = metadata.get(
        "storage_date"
    )

    if isinstance(
        raw,
        str,
    ):
        try:
            return date.fromisoformat(
                raw
            )
        except ValueError:
            pass

    if row["captured_at"] is not None:
        return row[
            "captured_at"
        ].date()

    return row[
        "created_at"
    ].date()


def _migrate_media(
    *,
    dry_run: bool,
    delete_old: bool,
    limit: int,
) -> tuple[int, int]:
    rows = _media_rows()

    if limit > 0:
        rows = rows[:limit]

    completed = 0
    failed = 0

    for index, row in enumerate(
        rows,
        start=1,
    ):
        media_id = UUID(
            str(
                row["media_id"]
            )
        )

        field_id = UUID(
            str(
                row["field_id"]
            )
        )

        context = (
            get_field_storage_context(
                field_id
            )
        )

        storage_date = (
            _media_storage_date(
                row
            )
        )

        prefix = media_prefix(
            context=context,
            storage_date=(
                storage_date
            ),
            media_id=media_id,
        )

        old_original_key = str(
            row["object_key"]
        )

        original_suffix = (
            Path(
                old_original_key
            )
            .suffix
            .lower()
        )

        if not original_suffix:
            original_suffix = (
                Path(
                    row[
                        "original_filename"
                    ]
                )
                .suffix
                .lower()
            )

        new_original_key = (
            f"{prefix}/original"
            f"{original_suffix}"
        )

        old_preview_key = (
            str(
                row[
                    "thumbnail_object_key"
                ]
            )
            if row[
                "thumbnail_object_key"
            ]
            else None
        )

        new_preview_key = (
            f"{prefix}/"
            f"{Path(old_preview_key).name}"
            if old_preview_key
            else None
        )

        old_bucket_name = (
            row["bucket_name"]
            or gcs_bucket().name
        )

        print(
            f"[media {index}/{len(rows)}] "
            f"{context['farm_name']} / "
            f"{context['field_name']} / "
            f"{storage_date}"
        )

        print(
            "    "
            f"{old_original_key}"
            " → "
            f"{new_original_key}"
        )

        if dry_run:
            continue

        try:
            _copy_verified(
                source_bucket_name=(
                    old_bucket_name
                ),
                source_key=(
                    old_original_key
                ),
                destination_bucket_name=(
                    gcs_bucket().name
                ),
                destination_key=(
                    new_original_key
                ),
            )

            if (
                old_preview_key
                and new_preview_key
            ):
                _copy_verified(
                    source_bucket_name=(
                        old_bucket_name
                    ),
                    source_key=(
                        old_preview_key
                    ),
                    destination_bucket_name=(
                        gcs_bucket().name
                    ),
                    destination_key=(
                        new_preview_key
                    ),
                )

            metadata = {
                **(
                    row[
                        "metadata_json"
                    ]
                    or {}
                ),
                "storage_layout_version":
                    STORAGE_LAYOUT_VERSION,
                "storage_date":
                    storage_date.isoformat(),
            }

            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE media_assets
                        SET
                            bucket_name = :bucket_name,
                            object_key = :object_key,
                            thumbnail_object_key = :thumbnail_object_key,
                            metadata_json =
                                CAST(
                                    :metadata_json
                                    AS jsonb
                                ),
                            updated_at = NOW()
                        WHERE id = :media_id
                        """
                    ),
                    {
                        "media_id":
                            media_id,
                        "bucket_name":
                            gcs_bucket().name,
                        "object_key":
                            new_original_key,
                        "thumbnail_object_key":
                            new_preview_key,
                        "metadata_json":
                            json.dumps(
                                metadata
                            ),
                    },
                )

            write_media_manifest_from_database(
                media_id=media_id
            )

            if delete_old:
                _delete_old(
                    old_bucket_name=(
                        old_bucket_name
                    ),
                    old_key=(
                        old_original_key
                    ),
                    new_bucket_name=(
                        gcs_bucket().name
                    ),
                    new_key=(
                        new_original_key
                    ),
                )

                if (
                    old_preview_key
                    and new_preview_key
                ):
                    _delete_old(
                        old_bucket_name=(
                            old_bucket_name
                        ),
                        old_key=(
                            old_preview_key
                        ),
                        new_bucket_name=(
                            gcs_bucket().name
                        ),
                        new_key=(
                            new_preview_key
                        ),
                    )

                old_manifest = (
                    f"{old_original_key.rsplit('/', 1)[0]}"
                    "/manifest.json"
                )

                try:
                    _delete_old(
                        old_bucket_name=(
                            old_bucket_name
                        ),
                        old_key=(
                            old_manifest
                        ),
                        new_bucket_name=(
                            gcs_bucket().name
                        ),
                        new_key=(
                            f"{prefix}/manifest.json"
                        ),
                    )
                except Exception:
                    pass

            completed += 1

        except Exception as error:
            failed += 1

            print(
                "    FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    return completed, failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate existing private GCS objects "
            "to Farm Platform storage layout v2."
        )
    )

    parser.add_argument(
        "--kind",
        choices=(
            "all",
            "satellite",
            "media",
        ),
        default="all",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Maximum observations/media rows "
            "per selected kind. 0 means all."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--delete-old",
        action="store_true",
        help=(
            "Delete old objects only after copy verification, "
            "DB update and manifest generation succeed."
        ),
    )

    args = parser.parse_args()

    sat_completed = 0
    sat_failed = 0
    media_completed = 0
    media_failed = 0

    if args.kind in (
        "all",
        "satellite",
    ):
        (
            sat_completed,
            sat_failed,
        ) = _migrate_satellite(
            dry_run=args.dry_run,
            delete_old=(
                args.delete_old
            ),
            limit=args.limit,
        )

    if args.kind in (
        "all",
        "media",
    ):
        (
            media_completed,
            media_failed,
        ) = _migrate_media(
            dry_run=args.dry_run,
            delete_old=(
                args.delete_old
            ),
            limit=args.limit,
        )

    print()
    print(
        "=================================="
    )
    print(
        "Storage layout v2 migration"
    )
    print(
        "=================================="
    )

    print(
        "Satellite completed: "
        f"{sat_completed}"
    )
    print(
        "Satellite failed:    "
        f"{sat_failed}"
    )
    print(
        "Media completed:     "
        f"{media_completed}"
    )
    print(
        "Media failed:        "
        f"{media_failed}"
    )

    if args.dry_run:
        print(
            "Dry run only. "
            "No objects or DB rows changed."
        )

    if (
        sat_failed
        or media_failed
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
