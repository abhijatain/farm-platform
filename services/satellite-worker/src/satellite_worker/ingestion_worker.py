from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import UUID

from satellite_worker.config import settings
from satellite_worker.db import (
    claim_next_satellite_ingestion_job,
    enqueue_incremental_satellite_jobs,
    mark_satellite_ingestion_job_completed,
    mark_satellite_ingestion_job_failed,
    recover_stale_satellite_ingestion_jobs,
)


def _enqueue_incremental_jobs() -> int:
    return enqueue_incremental_satellite_jobs(
        end_date=datetime.now(
            timezone.utc
        ).date(),
        lookback_days=(
            settings
            .satellite_incremental_lookback_days
        ),
        max_attempts=(
            settings
            .satellite_job_max_attempts
        ),
    )


def _process_job(
    job: dict,
) -> bool:
    job_id = UUID(
        str(
            job[
                "id"
            ]
        )
    )

    field_id = UUID(
        str(
            job[
                "field_id"
            ]
        )
    )

    print()
    print(
        "========================================"
    )
    print(
        "Satellite ingestion job"
    )
    print(
        f"Job:   {job_id}"
    )
    print(
        f"Field: {field_id}"
    )
    print(
        "Type:  "
        f"{job['job_type']}"
    )
    print(
        "Range: "
        f"{job['start_date']} "
        "→ "
        f"{job['end_date']}"
    )
    print(
        "Attempt: "
        f"{job['attempts']}/"
        f"{job['max_attempts']}"
    )
    print(
        "========================================"
    )

    command = [
        sys.executable,
        "-m",
        "satellite_worker.process_field",
        "--field-id",
        str(
            field_id
        ),
        "--start",
        job[
            "start_date"
        ].isoformat(),
        "--end",
        job[
            "end_date"
        ].isoformat(),
        "--max-scene-cloud",
        str(
            settings
            .satellite_max_scene_cloud
        ),
        "--limit",
        str(
            settings
            .satellite_scene_limit
        ),
        "--skip-existing",
    ]

    try:
        result = subprocess.run(
            command,
            check=False,
        )

    except Exception as error:
        message = (
            "Unable to launch process_field: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        print(
            message
        )

        mark_satellite_ingestion_job_failed(
            job_id=job_id,
            error_message=message,
            retry_delay_minutes=(
                settings
                .satellite_job_retry_delay_minutes
            ),
        )

        return False

    if result.returncode == 0:
        mark_satellite_ingestion_job_completed(
            job_id
        )

        print(
            "Ingestion job completed."
        )

        return True

    message = (
        "process_field exited with "
        f"status {result.returncode}"
    )

    mark_satellite_ingestion_job_failed(
        job_id=job_id,
        error_message=message,
        retry_delay_minutes=(
            settings
            .satellite_job_retry_delay_minutes
        ),
    )

    print(
        "Ingestion job failed; "
        "retry will follow if attempts remain."
    )

    return False


def _run_once() -> None:
    recovered = (
        recover_stale_satellite_ingestion_jobs(
            stale_after_minutes=(
                settings
                .satellite_job_stale_after_minutes
            )
        )
    )

    if recovered:
        print(
            "Recovered stale satellite jobs: "
            f"{recovered}"
        )

    inserted = (
        _enqueue_incremental_jobs()
    )

    if inserted:
        print(
            "Queued incremental satellite jobs: "
            f"{inserted}"
        )

    while True:
        job = (
            claim_next_satellite_ingestion_job()
        )

        if job is None:
            break

        _process_job(
            job
        )


def _run_forever() -> None:
    print(
        "Automatic satellite ingestion worker started."
    )

    recovered = (
        recover_stale_satellite_ingestion_jobs(
            stale_after_minutes=(
                settings
                .satellite_job_stale_after_minutes
            )
        )
    )

    if recovered:
        print(
            "Recovered stale satellite jobs: "
            f"{recovered}"
        )

    enqueue_interval_seconds = max(
        60,
        settings
        .satellite_incremental_enqueue_interval_minutes
        * 60,
    )

    next_incremental_enqueue_at = 0.0

    try:
        while True:
            now = (
                time.monotonic()
            )

            if (
                now
                >= next_incremental_enqueue_at
            ):
                inserted = (
                    _enqueue_incremental_jobs()
                )

                if inserted:
                    print(
                        "Queued incremental satellite jobs: "
                        f"{inserted}"
                    )

                next_incremental_enqueue_at = (
                    now
                    + enqueue_interval_seconds
                )

            job = (
                claim_next_satellite_ingestion_job()
            )

            if job is not None:
                _process_job(
                    job
                )

                continue

            time.sleep(
                max(
                    1.0,
                    settings
                    .satellite_job_poll_seconds,
                )
            )

    except KeyboardInterrupt:
        print()
        print(
            "Automatic satellite ingestion worker stopped."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously process automatic Sentinel-2 ingestion jobs."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Enqueue today's incremental jobs, drain the current queue, "
            "then exit. Useful for cron or Cloud Run Jobs."
        ),
    )

    args = parser.parse_args()

    if args.once:
        _run_once()
    else:
        _run_forever()


if __name__ == "__main__":
    main()
