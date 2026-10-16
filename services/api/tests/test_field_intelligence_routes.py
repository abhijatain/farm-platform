"""PostGIS-backed ownership, monthly sampling and growth context routes."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon, MultiPolygon

from app.api.routes import field_intelligence
from app.db.session import SessionLocal
from app.models.user import User
from app.models.farm import Farm
from app.models.field import Field
from app.models.season import Season
from app.models.crop_cycle import CropCycle
from app.models.satellite_observation import SatelliteObservation
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_anomaly import SatelliteAnomaly


def _create_fixture(db):
    suffix = str(uuid4())
    user = User(
        firebase_uid="zone-owner-" + suffix,
        phone_e164="+91" + str(uuid4().int)[:10],
        preferred_language="en",
    )
    db.add(user)
    db.flush()
    farm = Farm(owner_user_id=user.id, name="Zone test farm " + suffix[:6])
    db.add(farm)
    db.flush()
    boundary = Polygon([
        (76.700, 30.700), (76.705, 30.700),
        (76.705, 30.705), (76.700, 30.705),
        (76.700, 30.700),
    ])
    field = Field(farm_id=farm.id, name="Rice zone test", boundary=from_shape(boundary, srid=4326))
    db.add(field)
    db.flush()
    season = Season(farm_id=farm.id, name="Kharif 2026", started_on=date(2026, 6, 1), status="active")
    db.add(season)
    db.flush()
    crop = CropCycle(
        season_id=season.id, field_id=field.id, crop_name="rice",
        planted_on=date(2026, 6, 1), started_on=date(2026, 6, 1),
        status="active",
    )
    db.add(crop)
    db.flush()
    older_season = Season(
        farm_id=farm.id, name="Kharif 2025",
        started_on=date(2025, 6, 1), status="completed",
    )
    db.add(older_season)
    db.flush()
    db.add(CropCycle(
        season_id=older_season.id, field_id=field.id, crop_name="rice",
        planted_on=date(2025, 6, 1), started_on=date(2025, 6, 1),
        status="completed", harvested_on=date(2025, 11, 1),
    ))
    footprint = MultiPolygon([Polygon([
        (76.700, 30.700), (76.703, 30.700),
        (76.703, 30.705), (76.700, 30.705),
        (76.700, 30.700),
    ])])
    for acquisition in (
        date(2024, 9, 1), date(2025, 9, 1),
        date(2025, 10, 15), date(2026, 10, 1),
    ):
        observation = SatelliteObservation(
            field_id=field.id, source="sentinel-2",
            observed_on=acquisition, scene_id="scene-" + str(uuid4()),
            metadata_json={"processing_status": "metrics_processed"},
        )
        db.add(observation)
        db.flush()
        db.add(SatelliteMetric(
            satellite_observation_id=observation.id, metric_type="ndvi",
            raster_uri="gs://test/not-accessed.tif",
            mean=0.5, median=0.5,
            valid_pixel_count=80, pixel_count=90,
            valid_pixel_percent=95.0,
            native_resolution_m=10, output_resolution_m=20,
            metadata_json={},
        ))
        db.add(SatelliteAnomaly(
            satellite_observation_id=observation.id,
            index_type="ndvi", zone_index=0,
            anomaly_type="below_field_baseline",
            severity="moderate", geometry=from_shape(footprint, srid=4326),
            pixel_count=20, area_sqm=15000, area_acres=3.7,
            zone_mean_value=0.3, zone_min_value=0.2,
            field_mean_value=0.5, field_median_value=0.5,
            threshold_value=0.4, difference_from_field=-0.2,
            detection_method="robust_mad_metric_v1", metadata_json={},
        ))
    db.flush()
    return user, field, crop


def test_owner_restricted_spatial_zone_history_and_maturity(monkeypatch):
    monkeypatch.setattr(field_intelligence, "_today", lambda: date(2026, 10, 16))
    db = SessionLocal()
    try:
        owner, field, crop = _create_fixture(db)
        result = field_intelligence.spatial_history(
            field.id, db, owner, metric_type="ndvi", years=5
        )
        assert result["field_id"] == str(field.id)
        assert result["sampling"] == "monthly_best_plus_recent_4"
        assert result["observation_count"] >= 3
        assert result["tracking"]
        assert result["status"] == "short_history"
        assert result["zones"] == []

        sensors = field_intelligence.observation_intelligence(
            field.id, db, owner, years=3,
        )
        comparable = [c for c in sensors["comparisons"] if c["metric_type"] == "ndvi"]
        assert comparable and comparable[0]["status"] == "complete"

        phen = field_intelligence.phenology_intelligence(crop.id, db, owner)
        assert phen["profile_key"] == "rice"
        assert phen["stage_source"] == "provisional_calendar"
        assert phen["historical_comparisons"]

        with pytest.raises(HTTPException) as denied:
            field_intelligence.spatial_history(
                field.id, db, User(id=uuid4()), metric_type="ndvi", years=5,
            )
        assert denied.value.status_code == 404
    finally:
        db.rollback()
        db.close()
