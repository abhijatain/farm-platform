"""Backwards-compatible satellite database function imports.

New code should use persistence.scenes or persistence.jobs directly.
"""

from satellite_worker.persistence.connection import engine
from satellite_worker.persistence.scenes import (
    get_field_geometry,
    save_satellite_observation,
    save_satellite_metrics,
    replace_satellite_anomalies,
    list_satellite_metric_rasters_for_backfill,
    automatic_scene_state_is_complete,
    satellite_scene_is_complete_for_automatic_ingestion,
    satellite_scene_is_handled_for_metrics,
)
from satellite_worker.persistence.jobs import (
    enqueue_missing_initial_satellite_jobs,
    enqueue_missing_multisource_backfill_jobs,
    enqueue_incremental_satellite_jobs,
    claim_next_satellite_ingestion_job,
    mark_satellite_ingestion_job_completed,
    mark_satellite_ingestion_job_failed,
    recover_stale_satellite_ingestion_jobs,
)

__all__ = [
    "engine",
    "get_field_geometry",
    "save_satellite_observation",
    "save_satellite_metrics",
    "replace_satellite_anomalies",
    "list_satellite_metric_rasters_for_backfill",
    "automatic_scene_state_is_complete",
    "satellite_scene_is_complete_for_automatic_ingestion",
    "enqueue_missing_initial_satellite_jobs",
    "enqueue_missing_multisource_backfill_jobs",
    "enqueue_incremental_satellite_jobs",
    "claim_next_satellite_ingestion_job",
    "mark_satellite_ingestion_job_completed",
    "mark_satellite_ingestion_job_failed",
    "recover_stale_satellite_ingestion_jobs",
    "satellite_scene_is_handled_for_metrics",
]
