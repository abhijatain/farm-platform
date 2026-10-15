"""Queue lifecycle: enqueue, claim, retry and recover satellite processing jobs.

Jobs share the worker SQLAlchemy engine, but not scene persistence logic.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from satellite_worker.persistence.connection import engine


def enqueue_missing_initial_satellite_jobs(
    *,
    end_date: date,
    backfill_days: int,
    max_attempts: int,
) -> int:
    """
    Bootstrap fields that existed before automatic ingestion was deployed.

    Only fields with zero satellite observations are eligible, so historical
    NDVI-only fields are never treated as missing or backfilled.
    """

    backfill_days = max(
        1,
        backfill_days,
    )

    start_date = (
        end_date
        - timedelta(
            days=backfill_days - 1
        )
    )

    with engine.begin() as connection:
        field_ids = connection.execute(
            text(
                """
                SELECT
                    field.id

                FROM fields AS field

                WHERE NOT EXISTS (
                    SELECT 1

                    FROM satellite_metrics
                        AS metric

                    JOIN satellite_observations
                        AS observation
                      ON observation.id =
                            metric.satellite_observation_id

                    WHERE observation.field_id =
                        field.id
                )

                ORDER BY field.created_at
                """
            )
        ).scalars().all()

        inserted = 0

        for field_id in field_ids:
            result = connection.execute(
                text(
                    """
                    INSERT INTO satellite_ingestion_jobs (
                        id,
                        field_id,
                        job_type,
                        start_date,
                        end_date,
                        status,
                        attempts,
                        max_attempts,
                        available_at,
                        dedupe_key,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :id,
                        :field_id,
                        'initial_backfill',
                        :start_date,
                        :end_date,
                        'pending',
                        0,
                        :max_attempts,
                        NOW(),
                        :dedupe_key,
                        NOW(),
                        NOW()
                    )

                    ON CONFLICT (
                        dedupe_key
                    )
                    DO NOTHING
                    """
                ),
                {
                    "id":
                        uuid4(),
                    "field_id":
                        field_id,
                    "start_date":
                        start_date,
                    "end_date":
                        end_date,
                    "max_attempts":
                        max_attempts,
                    "dedupe_key":
                        (
                            "initial_backfill:"
                            f"{field_id}"
                        ),
                },
            )

            inserted += max(
                0,
                result.rowcount
                or 0,
            )

    return inserted


def enqueue_missing_multisource_backfill_jobs(
    *,
    end_date: date,
    backfill_days: int,
    max_attempts: int,
) -> int:
    """
    One-time rollout backfill for fields that already had optical metric data
    before Sentinel-1 radar and Landsat thermal ingestion were introduced.

    Empty/new fields are handled by the normal initial-backfill queue.
    """

    backfill_days = max(
        1,
        backfill_days,
    )

    start_date = (
        end_date
        - timedelta(
            days=backfill_days - 1
        )
    )

    with engine.begin() as connection:
        field_ids = connection.execute(
            text(
                """
                SELECT
                    field.id

                FROM fields AS field

                WHERE EXISTS (
                    SELECT 1

                    FROM satellite_metrics
                        AS existing_metric

                    JOIN satellite_observations
                        AS existing_observation
                      ON existing_observation.id =
                            existing_metric.satellite_observation_id

                    WHERE existing_observation.field_id =
                        field.id
                )

                AND (
                    NOT EXISTS (
                        SELECT 1

                        FROM satellite_metrics
                            AS radar_metric

                        JOIN satellite_observations
                            AS radar_observation
                          ON radar_observation.id =
                                radar_metric.satellite_observation_id

                        WHERE radar_observation.field_id =
                            field.id

                        AND radar_metric.metric_type IN (
                            'sar_vv_db',
                            'sar_vh_db',
                            'sar_vv_vh_ratio',
                            'sar_rvi'
                        )
                    )

                    OR NOT EXISTS (
                        SELECT 1

                        FROM satellite_metrics
                            AS thermal_metric

                        JOIN satellite_observations
                            AS thermal_observation
                          ON thermal_observation.id =
                                thermal_metric.satellite_observation_id

                        WHERE thermal_observation.field_id =
                            field.id

                        AND thermal_metric.metric_type =
                            'lst_c'
                    )
                )

                ORDER BY field.created_at
                """
            )
        ).scalars().all()

        inserted = 0

        for field_id in field_ids:
            result = connection.execute(
                text(
                    """
                    INSERT INTO satellite_ingestion_jobs (
                        id,
                        field_id,
                        job_type,
                        start_date,
                        end_date,
                        status,
                        attempts,
                        max_attempts,
                        available_at,
                        dedupe_key,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :id,
                        :field_id,
                        'initial_backfill',
                        :start_date,
                        :end_date,
                        'pending',
                        0,
                        :max_attempts,
                        NOW(),
                        :dedupe_key,
                        NOW(),
                        NOW()
                    )

                    ON CONFLICT (
                        dedupe_key
                    )
                    DO NOTHING
                    """
                ),
                {
                    "id":
                        uuid4(),
                    "field_id":
                        field_id,
                    "start_date":
                        start_date,
                    "end_date":
                        end_date,
                    "max_attempts":
                        max_attempts,
                    "dedupe_key":
                        (
                            "multisource_backfill_v1:"
                            f"{field_id}"
                        ),
                },
            )

            inserted += max(
                0,
                result.rowcount
                or 0,
            )

    return inserted


def enqueue_incremental_satellite_jobs(
    *,
    end_date: date,
    lookback_days: int,
    max_attempts: int,
) -> int:
    """
    Enqueue one incremental job per field for the UTC date.

    The dedupe key makes this safe to run repeatedly throughout the day.
    """

    lookback_days = max(
        1,
        lookback_days,
    )

    start_date = (
        end_date
        - timedelta(
            days=lookback_days - 1
        )
    )

    with engine.begin() as connection:
        field_ids = connection.execute(
            text(
                """
                SELECT id
                FROM fields
                ORDER BY created_at
                """
            )
        ).scalars().all()

        inserted = 0

        for field_id in field_ids:
            result = connection.execute(
                text(
                    """
                    INSERT INTO satellite_ingestion_jobs (
                        id,
                        field_id,
                        job_type,
                        start_date,
                        end_date,
                        status,
                        attempts,
                        max_attempts,
                        available_at,
                        dedupe_key,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :id,
                        :field_id,
                        'incremental',
                        :start_date,
                        :end_date,
                        'pending',
                        0,
                        :max_attempts,
                        NOW(),
                        :dedupe_key,
                        NOW(),
                        NOW()
                    )

                    ON CONFLICT (
                        dedupe_key
                    )
                    DO NOTHING
                    """
                ),
                {
                    "id":
                        uuid4(),
                    "field_id":
                        field_id,
                    "start_date":
                        start_date,
                    "end_date":
                        end_date,
                    "max_attempts":
                        max_attempts,
                    "dedupe_key":
                        (
                            "incremental:"
                            f"{field_id}:"
                            f"{end_date.isoformat()}"
                        ),
                },
            )

            inserted += (
                result.rowcount
                or 0
            )

    return inserted


def claim_next_satellite_ingestion_job() -> dict | None:
    """
    Atomically claim the oldest runnable job.

    FOR UPDATE SKIP LOCKED permits multiple worker processes. A partial unique
    index additionally prevents two different jobs for the same field from
    being marked running at the same time.
    """

    query = text(
        """
        WITH candidate AS (
            SELECT
                job.id

            FROM satellite_ingestion_jobs AS job

            WHERE
                job.status = 'pending'

            AND job.available_at <= NOW()

            AND job.attempts
                < job.max_attempts

            AND NOT EXISTS (
                SELECT 1

                FROM satellite_ingestion_jobs AS running

                WHERE
                    running.field_id =
                        job.field_id

                AND running.status =
                        'running'
            )

            ORDER BY
                CASE
                    WHEN job.job_type =
                        'initial_backfill'
                    THEN 0
                    ELSE 1
                END,
                job.created_at

            FOR UPDATE SKIP LOCKED

            LIMIT 1
        )

        UPDATE satellite_ingestion_jobs AS job

        SET
            status = 'running',
            attempts =
                job.attempts + 1,
            started_at = NOW(),
            completed_at = NULL,
            last_error = NULL,
            updated_at = NOW()

        FROM candidate

        WHERE job.id =
            candidate.id

        RETURNING
            job.id,
            job.field_id,
            job.job_type,
            job.start_date,
            job.end_date,
            job.attempts,
            job.max_attempts
        """
    )

    try:
        with engine.begin() as connection:
            row = (
                connection.execute(
                    query
                )
                .mappings()
                .first()
            )

    except IntegrityError:
        # A second worker may have won the per-field running-job race after
        # candidate selection. The unique partial index is the final guard.
        return None

    if row is None:
        return None

    return dict(
        row
    )


def mark_satellite_ingestion_job_completed(
    job_id: UUID,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE satellite_ingestion_jobs

                SET
                    status = 'completed',
                    completed_at = NOW(),
                    last_error = NULL,
                    updated_at = NOW()

                WHERE id =
                    :job_id
                """
            ),
            {
                "job_id":
                    job_id,
            },
        )


def mark_satellite_ingestion_job_failed(
    *,
    job_id: UUID,
    error_message: str,
    retry_delay_minutes: int,
) -> None:
    retry_delay_seconds = max(
        0,
        retry_delay_minutes,
    ) * 60

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE satellite_ingestion_jobs

                SET
                    status =
                        CASE
                            WHEN attempts >=
                                max_attempts
                            THEN 'failed'
                            ELSE 'pending'
                        END,

                    available_at =
                        CASE
                            WHEN attempts >=
                                max_attempts
                            THEN available_at
                            ELSE
                                NOW()
                                + (
                                    :retry_delay_seconds
                                    * INTERVAL '1 second'
                                )
                        END,

                    started_at = NULL,

                    completed_at =
                        CASE
                            WHEN attempts >=
                                max_attempts
                            THEN NOW()
                            ELSE NULL
                        END,

                    last_error =
                        :error_message,

                    updated_at =
                        NOW()

                WHERE id =
                    :job_id
                """
            ),
            {
                "job_id":
                    job_id,
                "retry_delay_seconds":
                    retry_delay_seconds,
                "error_message":
                    error_message[
                        :4000
                    ],
            },
        )


def recover_stale_satellite_ingestion_jobs(
    *,
    stale_after_minutes: int,
) -> int:
    stale_seconds = max(
        1,
        stale_after_minutes,
    ) * 60

    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                UPDATE satellite_ingestion_jobs

                SET
                    status =
                        CASE
                            WHEN attempts >=
                                max_attempts
                            THEN 'failed'
                            ELSE 'pending'
                        END,

                    available_at =
                        NOW(),

                    started_at =
                        NULL,

                    completed_at =
                        CASE
                            WHEN attempts >=
                                max_attempts
                            THEN NOW()
                            ELSE NULL
                        END,

                    last_error =
                        CASE
                            WHEN attempts >=
                                max_attempts
                            THEN
                                'Recovered stale job; retry limit reached.'
                            ELSE
                                'Recovered stale running job.'
                        END,

                    updated_at =
                        NOW()

                WHERE
                    status = 'running'

                AND started_at <
                    NOW()
                    - (
                        :stale_seconds
                        * INTERVAL '1 second'
                    )
                """
            ),
            {
                "stale_seconds":
                    stale_seconds,
            },
        )

        return int(
            result.rowcount
            or 0
        )
