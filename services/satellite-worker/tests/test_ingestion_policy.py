from satellite_worker.db import (
    automatic_scene_state_is_complete,
)


def test_legacy_ndvi_only_scene_is_preserved() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="legacy-ndvi",
        metric_count=1,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_empty_legacy_scene_is_retryable() -> None:
    assert not automatic_scene_state_is_complete(
        processing_version="legacy-ndvi",
        metric_count=0,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_complete_v2_scene_is_skipped() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        metric_count=13,
        anomaly_analysis_count=13,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_incomplete_v2_scene_is_reprocessed() -> None:
    assert not automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        metric_count=13,
        anomaly_analysis_count=12,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_failed_v2_anomaly_scene_is_reprocessed() -> None:
    assert not automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        metric_count=13,
        anomaly_analysis_count=13,
        failed_anomaly_count=1,
        expected_metric_count=13,
    )
