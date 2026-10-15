"""Resolve farm and field storage identifiers needed by satellite jobs."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text

from satellite_worker.persistence.connection import engine


def get_field_storage_context(
    field_id: UUID,
) -> dict:
    query = text(
        """
        SELECT
            u.id AS user_id,
            u.name AS user_name,
            u.phone_e164 AS phone_e164,
            u.preferred_language AS preferred_language,

            fa.id AS farm_id,
            fa.name AS farm_name,
            fa.storage_slug AS farm_storage_slug,
            fa.location_name AS farm_location_name,
            fa.created_at AS farm_created_at,
            fa.updated_at AS farm_updated_at,

            f.id AS field_id,
            f.name AS field_name,
            f.storage_slug AS field_storage_slug,
            f.created_at AS field_created_at,
            f.updated_at AS field_updated_at,

            ST_AsGeoJSON(f.boundary)
                AS field_boundary

        FROM fields AS f

        JOIN farms AS fa
            ON fa.id = f.farm_id

        JOIN users AS u
            ON u.id = fa.owner_user_id

        WHERE f.id = :field_id
        """
    )

    with engine.connect() as connection:
        row = (
            connection.execute(
                query,
                {
                    "field_id":
                        field_id,
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise ValueError(
            f"Field not found: {field_id}"
        )

    result = dict(row)

    boundary = result[
        "field_boundary"
    ]

    if isinstance(
        boundary,
        str,
    ):
        boundary = json.loads(
            boundary
        )

    result[
        "field_boundary"
    ] = boundary

    return result
