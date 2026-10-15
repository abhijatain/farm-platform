"""Refresh cloud recovery manifests for stored field media."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.media_asset import MediaAsset
from app.storage.manifests import (
    write_media_manifests,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite recovery manifests for "
            "all farmer media using the current schema."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="0 means all ready media.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db = SessionLocal()

    try:
        statement = (
            select(MediaAsset)
            .where(
                MediaAsset.status
                == "ready"
            )
            .order_by(
                MediaAsset.created_at
            )
        )

        if args.limit > 0:
            statement = (
                statement.limit(
                    args.limit
                )
            )

        rows = list(
            db.scalars(
                statement
            ).all()
        )

        print(
            "Ready media manifests to refresh: "
            f"{len(rows)}"
        )

        failed = 0

        for index, media in enumerate(
            rows,
            start=1,
        ):
            try:
                write_media_manifests(
                    db=db,
                    media=media,
                )

                print(
                    f"[{index}/{len(rows)}] "
                    f"{media.id} ✓"
                )

            except Exception as error:
                failed += 1

                print(
                    f"[{index}/{len(rows)}] "
                    f"{media.id} FAILED: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

    finally:
        db.close()

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
