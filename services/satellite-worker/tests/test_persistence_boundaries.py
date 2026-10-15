"""Verify that scene storage and ingestion jobs share one database engine.

The database repositories are separate real implementations, not forwarding
modules. This prevents accidentally creating independent connection pools.
"""

from satellite_worker.persistence import connection, jobs, scenes


def test_scene_repository_is_canonical():
    assert scenes.engine is connection.engine
    assert callable(scenes.get_field_geometry)
    assert callable(scenes.save_satellite_metrics)
    assert callable(scenes.replace_satellite_anomalies)
    assert callable(scenes.satellite_scene_is_handled_for_metrics)


def test_job_repository_is_canonical():
    assert jobs.engine is connection.engine
    assert callable(jobs.enqueue_incremental_satellite_jobs)
    assert callable(jobs.claim_next_satellite_ingestion_job)
    assert callable(jobs.mark_satellite_ingestion_job_failed)
    assert callable(jobs.recover_stale_satellite_ingestion_jobs)
