"""Check source-specific cloudy dates and radar fallback selection."""

from datetime import date, datetime, timezone
from uuid import uuid4

from app.models.satellite_metric import (
    SatelliteMetric,
)
from app.models.satellite_observation import (
    SatelliteObservation,
)
from app.domains.satellite.timeline import (
    build_satellite_timeline,
    source_kind,
    timeline_status,
)


def _observation(
    *,
    field_id,
    observed_on: date,
    source: str,
    processing_status: str,
    metrics: list[
        SatelliteMetric
    ],
) -> SatelliteObservation:
    observation = SatelliteObservation(
        id=uuid4(),
        field_id=field_id,
        observed_on=observed_on,
        source=source,
        scene_id=(
            f"{source}-"
            f"{observed_on.isoformat()}"
        ),
        cloud_cover_percent=None,
        metadata_json={
            "processing_status":
                processing_status,
        },
    )

    observation.created_at = (
        datetime(
            observed_on.year,
            observed_on.month,
            observed_on.day,
            tzinfo=timezone.utc,
        )
    )

    observation.metrics = (
        metrics
    )

    return observation


def _metric(
    metric_type: str,
    *,
    median: float,
    valid_percent: float = 100.0,
) -> SatelliteMetric:
    return SatelliteMetric(
        id=uuid4(),
        satellite_observation_id=uuid4(),
        metric_type=metric_type,
        raster_uri=(
            f"gs://bucket/{metric_type}.tif"
        ),
        mean=median,
        median=median,
        min=median,
        max=median,
        std=0.0,
        native_resolution_m=10.0,
        output_resolution_m=10.0,
        pixel_count=100,
        valid_pixel_count=100,
        valid_pixel_percent=(
            valid_percent
        ),
        metadata_json={},
    )


def test_source_kind_classifies_supported_sensors() -> None:
    assert (
        source_kind(
            "sentinel-2"
        )
        == "optical"
    )

    assert (
        source_kind(
            "sentinel-1-rtc"
        )
        == "radar"
    )

    assert (
        source_kind(
            "landsat-c2-l2"
        )
        == "thermal"
    )


def test_cloud_skipped_observation_stays_in_timeline() -> None:
    field_id = uuid4()

    cloudy = _observation(
        field_id=field_id,
        observed_on=date(
            2026,
            10,
            10,
        ),
        source="sentinel-2",
        processing_status=(
            "skipped_scene_cloud_cover"
        ),
        metrics=[],
    )

    assert (
        timeline_status(
            cloudy
        )
        == "cloud_skipped"
    )

    timeline = (
        build_satellite_timeline(
            field_id=field_id,
            observations=[
                cloudy
            ],
            preferred_metric_type="ndvi",
            target_date=date(
                2026,
                10,
                10,
            ),
            minimum_valid_percent=80.0,
            window_days=14,
        )
    )

    assert (
        timeline.events[
            0
        ].status
        == "cloud_skipped"
    )

    assert (
        timeline.events[
            0
        ].source_kind
        == "optical"
    )


def test_radar_is_recommended_when_target_optical_is_cloudy() -> None:
    field_id = uuid4()

    clear_optical = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            source="sentinel-2",
            processing_status=(
                "metrics_processed"
            ),
            metrics=[
                _metric(
                    "ndvi",
                    median=0.62,
                )
            ],
        )
    )

    cloudy_optical = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                10,
            ),
            source="sentinel-2",
            processing_status=(
                "skipped_scene_cloud_cover"
            ),
            metrics=[],
        )
    )

    radar = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                11,
            ),
            source="sentinel-1-rtc",
            processing_status=(
                "metrics_processed"
            ),
            metrics=[
                _metric(
                    "sar_rvi",
                    median=0.81,
                )
            ],
        )
    )

    timeline = (
        build_satellite_timeline(
            field_id=field_id,
            observations=[
                clear_optical,
                cloudy_optical,
                radar,
            ],
            preferred_metric_type="ndvi",
            target_date=date(
                2026,
                10,
                10,
            ),
            minimum_valid_percent=80.0,
            window_days=14,
        )
    )

    selection = (
        timeline.selection
    )

    assert (
        selection
        .optical_unavailable_on_target
    )

    assert (
        selection
        .preferred_metric
        is not None
    )

    assert (
        selection
        .preferred_metric
        .metric_type
        == "ndvi"
    )

    assert (
        selection
        .preferred_metric
        .observed_on
        == date(
            2026,
            10,
            5,
        )
    )

    assert (
        selection
        .radar_fallback
        is not None
    )

    assert (
        selection
        .radar_fallback
        .metric_type
        == "sar_rvi"
    )

    assert (
        selection
        .recommended_kind
        == "radar_fallback"
    )

    assert (
        selection
        .recommended
        is not None
    )

    assert (
        selection
        .recommended
        .metric_type
        == "sar_rvi"
    )


def test_usable_preferred_metric_wins_on_target_date() -> None:
    field_id = uuid4()

    optical = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                14,
            ),
            source="sentinel-2",
            processing_status=(
                "metrics_processed"
            ),
            metrics=[
                _metric(
                    "ndvi",
                    median=0.74,
                )
            ],
        )
    )

    radar = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                13,
            ),
            source="sentinel-1-rtc",
            processing_status=(
                "metrics_processed"
            ),
            metrics=[
                _metric(
                    "sar_rvi",
                    median=0.9,
                )
            ],
        )
    )

    timeline = (
        build_satellite_timeline(
            field_id=field_id,
            observations=[
                optical,
                radar,
            ],
            preferred_metric_type="ndvi",
            target_date=date(
                2026,
                10,
                14,
            ),
            minimum_valid_percent=80.0,
            window_days=14,
        )
    )

    assert (
        timeline.selection
        .recommended_kind
        == "preferred_metric"
    )

    assert (
        timeline.selection
        .recommended
        is not None
    )

    assert (
        timeline.selection
        .recommended
        .metric_type
        == "ndvi"
    )



def test_default_target_uses_latest_optical_attempt() -> None:
    field_id = uuid4()

    cloudy_optical = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                10,
            ),
            source="sentinel-2",
            processing_status=(
                "skipped_scene_cloud_cover"
            ),
            metrics=[],
        )
    )

    radar = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                11,
            ),
            source="sentinel-1-rtc",
            processing_status=(
                "metrics_processed"
            ),
            metrics=[
                _metric(
                    "sar_rvi",
                    median=0.83,
                )
            ],
        )
    )

    older_optical = (
        _observation(
            field_id=field_id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            source="sentinel-2",
            processing_status=(
                "metrics_processed"
            ),
            metrics=[
                _metric(
                    "ndvi",
                    median=0.61,
                )
            ],
        )
    )

    timeline = (
        build_satellite_timeline(
            field_id=field_id,
            observations=[
                radar,
                cloudy_optical,
                older_optical,
            ],
            preferred_metric_type="ndvi",
            target_date=None,
            minimum_valid_percent=80.0,
            window_days=14,
        )
    )

    assert (
        timeline.selection
        .target_date
        == date(
            2026,
            10,
            10,
        )
    )

    assert (
        timeline.selection
        .recommended_kind
        == "radar_fallback"
    )
