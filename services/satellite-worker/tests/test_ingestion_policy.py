"""Regression tests for ingestion policy, protecting established satellite behavior."""

from satellite_worker.persistence.scenes import (
    automatic_scene_state_is_complete,
)


def test_legacy_ndvi_only_scene_is_preserved() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="legacy-ndvi",
        processing_status=None,
        metric_count=1,
        ndvi_metric_count=1,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_empty_legacy_scene_is_retryable() -> None:
    assert not automatic_scene_state_is_complete(
        processing_version="legacy-ndvi",
        processing_status=None,
        metric_count=0,
        ndvi_metric_count=0,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_complete_v2_scene_is_skipped() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        processing_status=None,
        metric_count=13,
        ndvi_metric_count=1,
        anomaly_analysis_count=13,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_incomplete_v2_scene_is_reprocessed() -> None:
    assert not automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        processing_status=None,
        metric_count=13,
        ndvi_metric_count=1,
        anomaly_analysis_count=12,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_failed_v2_anomaly_scene_is_reprocessed() -> None:
    assert not automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        processing_status=None,
        metric_count=13,
        ndvi_metric_count=1,
        anomaly_analysis_count=13,
        failed_anomaly_count=1,
        expected_metric_count=13,
    )


def test_ndvi_only_scene_is_preserved_even_with_v2_metadata() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        processing_status=None,
        metric_count=1,
        ndvi_metric_count=1,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_cloudy_scene_is_terminal_for_automatic_ingestion() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        processing_status="skipped_scene_cloud_cover",
        metric_count=0,
        ndvi_metric_count=0,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )


def test_no_usable_pixels_scene_is_terminal_for_automatic_ingestion() -> None:
    assert automatic_scene_state_is_complete(
        processing_version="sentinel2-metrics-v2",
        processing_status="skipped_no_usable_pixels",
        metric_count=0,
        ndvi_metric_count=0,
        anomaly_analysis_count=0,
        failed_anomaly_count=0,
        expected_metric_count=13,
    )
