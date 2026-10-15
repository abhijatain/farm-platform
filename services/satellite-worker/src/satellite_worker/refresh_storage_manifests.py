"""Rebuild cloud recovery metadata for stored satellite observations."""

from __future__ import annotations

import argparse
from uuid import UUID

from sqlalchemy import text

from satellite_worker.persistence.connection import engine
from satellite_worker.storage_context import (
    get_field_storage_context,
)
from satellite_worker.storage_manifests import (
    write_satellite_manifest_from_database,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite all satellite recovery manifests "
            "using the current canonical database schema."
        )
    )

    parser.add_argument(
        "--field-id",
        type=UUID,
        default=None,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="0 means all observations.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    clauses = []
    params: dict = {}

    if args.field_id is not None:
        clauses.append(
            "field_id = :field_id"
        )

        params[
            "field_id"
        ] = args.field_id

    where_sql = (
        "WHERE "
        + " AND ".join(
            clauses
        )
        if clauses
        else ""
    )

    limit_sql = ""

    if args.limit > 0:
        limit_sql = (
            "LIMIT :limit"
        )

        params[
            "limit"
        ] = args.limit

    query = text(
        f"""
        SELECT
            id,
            field_id,
            observed_on

        FROM satellite_observations

        {where_sql}

        ORDER BY
            observed_on,
            id

        {limit_sql}
        """
    )

    with engine.connect() as connection:
        rows = [
            dict(row)
            for row in (
                connection.execute(
                    query,
                    params,
                )
                .mappings()
                .all()
            )
        ]

    print(
        "Satellite manifests to refresh: "
        f"{len(rows)}"
    )

    context_cache: dict[
        UUID,
        dict,
    ] = {}

    failed = 0

    for index, row in enumerate(
        rows,
        start=1,
    ):
        observation_id = UUID(
            str(
                row[
                    "id"
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

        context = (
            context_cache.get(
                field_id
            )
        )

        if context is None:
            context = (
                get_field_storage_context(
                    field_id
                )
            )

            context_cache[
                field_id
            ] = context

        try:
            write_satellite_manifest_from_database(
                context=context,
                observation_id=(
                    observation_id
                ),
            )

            print(
                f"[{index}/{len(rows)}] "
                f"{row['observed_on']} "
                f"{observation_id} ✓"
            )

        except Exception as error:
            failed += 1

            print(
                f"[{index}/{len(rows)}] "
                f"{observation_id} FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
