"""Protect historical schema compatibility and core API invariants."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from pydantic import ValidationError
from shapely.geometry import Polygon

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.farm import Farm
from app.models.field import Field
from app.models.user import User
from app.schemas.crop_cycle import HarvestCropCycleRequest
from app.schemas.satellite_observation import (
    SatelliteMetricResponse,
    SatelliteObservationResponse,
)
from app.domains.satellite.ingestion import (
    enqueue_initial_satellite_backfill,
)


def test_legacy_ndvi_only_observation_is_valid() -> None:
    observation_id = uuid4()

    payload = SatelliteObservationResponse(
        id=observation_id,
        field_id=uuid4(),
        observed_on="2026-06-01",
        source="sentinel-2",
        scene_id="legacy-ndvi-scene",
        cloud_cover_percent=8.5,
        metadata_json={
            "processing_version": "legacy-ndvi",
            "private": {"object": "gs://not-for-browser/users/test/secret.tif"},
        },
        metrics=[
            SatelliteMetricResponse(
                id=uuid4(),
                satellite_observation_id=observation_id,
                metric_type="ndvi",
                raster_uri=(
                    "gs://farm-test/users/u/farms/f/fields/"
                    "field/dates/2026/06/01/satellite/o/ndvi.tif"
                ),
                mean=0.61,
                median=0.63,
                min=0.2,
                max=0.84,
                std=0.1,
                native_resolution_m=10.0,
                output_resolution_m=10.0,
                pixel_count=100,
                valid_pixel_count=95,
                valid_pixel_percent=95.0,
                metadata_json={},
            )
        ],
        created_at=datetime.now(
            timezone.utc
        ),
        updated_at=datetime.now(
            timezone.utc
        ),
    )

    assert [
        metric.metric_type
        for metric in payload.metrics
    ] == ["ndvi"]

    # API JSON must never expose raw private GCS URIs or signed storage paths.
    document = payload.model_dump(mode="json")
    assert document["metrics"][0]["has_raster"] is True
    assert "raster_uri" not in document["metrics"][0]
    assert "gs://" not in payload.model_dump_json()
    assert payload.model_dump()["metadata_json"]["private"]["object"] == "[private storage path]"


def test_harvest_timestamp_requires_timezone() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "harvested_at must include "
            "a timezone"
        ),
    ):
        HarvestCropCycleRequest(
            harvested_at=datetime(
                2026,
                10,
                14,
                12,
                0,
            ),
            yield_kg=1000,
            harvested_area_acres=1,
        )


def test_timezone_aware_harvest_timestamp_is_valid() -> None:
    request = HarvestCropCycleRequest(
        harvested_at=datetime(
            2026,
            10,
            14,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        yield_kg=1000,
        harvested_area_acres=1,
    )

    assert (
        request.harvested_at.utcoffset()
        is not None
    )


def test_new_field_queues_initial_satellite_backfill() -> None:
    db = SessionLocal()

    try:
        unique = str(
            uuid4()
        )

        user = User(
            firebase_uid=(
                "satellite-test-"
                + unique
            ),
            phone_e164=(
                "+91"
                + str(
                    uuid4().int
                )[:10]
            ),
            name="Satellite Test",
            preferred_language="en",
        )

        db.add(
            user
        )
        db.flush()

        farm = Farm(
            owner_user_id=user.id,
            name=(
                "Satellite Test Farm "
                + unique[:8]
            ),
            location_name=None,
        )

        db.add(
            farm
        )
        db.flush()

        field = Field(
            farm_id=farm.id,
            name=(
                "Satellite Test Field "
                + unique[:8]
            ),
            boundary=from_shape(
                Polygon(
                    [
                        (76.70, 30.70),
                        (76.71, 30.70),
                        (76.71, 30.71),
                        (76.70, 30.71),
                        (76.70, 30.70),
                    ]
                ),
                srid=4326,
            ),
        )

        db.add(
            field
        )
        db.flush()

        job = (
            enqueue_initial_satellite_backfill(
                field=field,
                db=db,
            )
        )

        db.flush()

        assert job.field_id == field.id
        assert job.job_type == "initial_backfill"
        assert job.status == "pending"
        assert (
            job.end_date
            - job.start_date
        ).days + 1 == (
            settings
            .satellite_initial_backfill_days
        )
        assert job.dedupe_key == (
            "initial_backfill:"
            f"{field.id}"
        )

    finally:
        db.rollback()
        db.close()



def test_raster_uri_absent_from_timeline_change_and_activity_responses():
    from app.schemas.satellite_timeline import (
        SatelliteTimelineMetricSummary, SatelliteTimelineSelectionMatch,
    )
    from app.schemas.satellite_change import SatelliteChangeObservation
    from app.schemas.activity_satellite import ActivitySatelliteObservationMatch

    uri = "gs://test-private-bucket/users/secret/ndvi.tif"
    metric = SatelliteTimelineMetricSummary(
        metric_type="ndvi", mean=0.5, median=0.51,
        valid_pixel_percent=95, raster_uri=uri,
    )
    selected = SatelliteTimelineSelectionMatch(
        observation_id=uuid4(), observed_on="2026-10-01",
        days_from_target=0, source="sentinel-2", source_kind="optical",
        metric_type="ndvi", median=0.51, mean=0.5,
        valid_pixel_percent=95, raster_uri=uri,
    )
    changed = SatelliteChangeObservation(
        observation_id=uuid4(), observed_on="2026-10-01",
        source="sentinel-2", scene_id="test", orbit_state=None,
        relative_orbit=None, platform=None, metric_type="ndvi",
        valid_pixel_percent=95, mean=0.5, median=0.51,
        minimum=0.1, maximum=0.8, std=0.12,
        raster_uri=uri, native_resolution_m=10,
        output_resolution_m=10,
    )
    activity = ActivitySatelliteObservationMatch(
        observation_id=uuid4(), observed_on="2026-10-01",
        days_from_activity=0, source="sentinel-2", scene_id="test",
        metric_type="ndvi", valid_pixel_percent=95,
        mean=0.5, median=0.51, minimum=0.1, maximum=0.8,
        std=0.12, raster_uri=uri,
        native_resolution_m=10, output_resolution_m=10,
        anomaly_zone_count=0, anomaly_area_sqm=0, anomaly_area_acres=0,
    )
    for obj in (metric, selected, changed, activity):
        serialized = obj.model_dump_json()
        assert "gs://" not in serialized
        assert "raster_uri" not in serialized
        assert obj.model_dump()["has_raster"] is True


def test_ingestion_job_error_does_not_reveal_private_raster_path():
    """Satellite worker exceptions may include private object names."""
    from app.schemas.satellite_observation import SatelliteIngestionJobResponse

    timestamp = datetime.now(timezone.utc)
    job = SatelliteIngestionJobResponse(
        id=uuid4(),
        field_id=uuid4(),
        job_type="initial_backfill",
        start_date="2026-10-01",
        end_date="2026-10-17",
        status="failed",
        attempts=3,
        max_attempts=3,
        available_at=timestamp,
        started_at=timestamp,
        completed_at=timestamp,
        last_error="Read failed: gs://private-bucket/users/owner/raster.tif",
        created_at=timestamp,
        updated_at=timestamp,
    )
    serialized = job.model_dump_json()
    assert "gs://" not in serialized
    assert "private-bucket" not in serialized
    assert job.model_dump()["last_error"] == "[private storage path]"
