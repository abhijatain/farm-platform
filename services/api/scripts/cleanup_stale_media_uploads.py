from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.media_asset import MediaAsset
from app.storage import get_storage
from app.storage.layout import media_manifest_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove stale pending/failed media rows and any associated "
            "objects left behind by interrupted browser uploads."
        )
    )

    parser.add_argument(
        "--older-than-hours",
        type=float,
        default=24.0,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    if args.older_than_hours <= 0:
        parser.error(
            "--older-than-hours must be greater than zero."
        )

    return args


def main() -> None:
    args = parse_args()

    cutoff = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            hours=args.older_than_hours
        )
    )

    db = SessionLocal()
    storage = get_storage()

    try:
        rows = list(
            db.scalars(
                select(
                    MediaAsset
                )
                .where(
                    MediaAsset.status.in_(
                        (
                            "pending",
                            "failed",
                        )
                    ),
                    MediaAsset.created_at
                    < cutoff,
                )
                .order_by(
                    MediaAsset.created_at
                    .asc()
                )
            ).all()
        )

        print(
            "Stale media rows: "
            f"{len(rows)}"
        )

        for media in rows:
            print(
                f"{media.id} "
                f"{media.status} "
                f"{media.created_at} "
                f"{media.original_filename}"
            )

            if args.dry_run:
                continue

            storage.delete(
                media.object_key
            )

            if media.preview_object_key:
                storage.delete(
                    media.preview_object_key
                )

            storage.delete(
                media_manifest_key(
                    media.object_key
                )
            )

            db.delete(
                media
            )

        if args.dry_run:
            db.rollback()
            print(
                "Dry run only. "
                "Nothing deleted."
            )
        else:
            db.commit()
            print("Cleanup complete.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
