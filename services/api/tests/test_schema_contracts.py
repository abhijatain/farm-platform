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
