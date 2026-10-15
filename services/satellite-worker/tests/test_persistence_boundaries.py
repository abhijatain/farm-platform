"""Protect worker database repository aliases and shared engine identity."""

from satellite_worker import db
from satellite_worker.persistence import connection, jobs, scenes


def test_scene_repository_compatibility_imports():
    assert db.engine is connection.engine
    assert db.get_field_geometry is scenes.get_field_geometry
    assert db.save_satellite_metrics is scenes.save_satellite_metrics
    assert db.replace_satellite_anomalies is scenes.replace_satellite_anomalies
    assert db.satellite_scene_is_handled_for_metrics is scenes.satellite_scene_is_handled_for_metrics


def test_queue_repository_compatibility_imports():
    assert db.enqueue_incremental_satellite_jobs is jobs.enqueue_incremental_satellite_jobs
    assert db.claim_next_satellite_ingestion_job is jobs.claim_next_satellite_ingestion_job
    assert db.mark_satellite_ingestion_job_failed is jobs.mark_satellite_ingestion_job_failed
    assert db.recover_stale_satellite_ingestion_jobs is jobs.recover_stale_satellite_ingestion_jobs
