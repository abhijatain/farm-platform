from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.field import Field
from app.models.satellite_ingestion_job import (
    SatelliteIngestionJob,
)


def enqueue_initial_satellite_backfill(
    *,
    field: Field,
    db: Session,
) -> SatelliteIngestionJob:
    """
    Queue the first historical Sentinel-2 ingestion for a newly-created field.

    The job is added to the caller's transaction so field creation and queue
    creation either commit together or roll back together.
    """

    if field.id is None:
        raise ValueError(
            "Field must be flushed before satellite ingestion is queued."
        )

    end_date = datetime.now(
        timezone.utc
    ).date()

    backfill_days = max(
        1,
        settings.satellite_initial_backfill_days,
    )

    start_date = (
        end_date
        - timedelta(
            days=backfill_days - 1
        )
    )

    job = SatelliteIngestionJob(
        field_id=field.id,
        job_type="initial_backfill",
        start_date=start_date,
        end_date=end_date,
        status="pending",
        attempts=0,
        max_attempts=3,
        dedupe_key=(
            "initial_backfill:"
            f"{field.id}"
        ),
    )

    db.add(
        job
    )

    return job
