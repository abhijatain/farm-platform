"""Process queued media conversions and thumbnails."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.media_asset import MediaAsset
from app.domains.media.processing import process_media_asset


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate thumbnails/posters and metadata "
            "for existing ready farmer media."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Maximum number of media assets to process. "
            "0 means all."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Rebuild derivatives even if processing "
            "already completed."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db = SessionLocal()

    try:
        statement = (
            select(
                MediaAsset.id
            )
            .where(
                MediaAsset.status
                == "ready"
            )
            .order_by(
                MediaAsset.created_at
                .asc()
            )
        )

        if args.limit > 0:
            statement = (
                statement.limit(
                    args.limit
                )
            )

        ids = list(
            db.scalars(
                statement
            ).all()
        )

    finally:
        db.close()

    print(
        f"Found {len(ids)} ready media assets."
    )

    for index, media_id in enumerate(
        ids,
        start=1,
    ):
        print(
            f"[{index}/{len(ids)}] "
            f"processing {media_id}"
        )

        process_media_asset(
            media_id,
            force=args.force,
        )

    print("Done.")


if __name__ == "__main__":
    main()
