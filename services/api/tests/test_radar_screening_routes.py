"""Owner scoping and weather-independent screening through the API route."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon

from app.api.routes.radar_screening import get_crop_radar_screening
from app.db.session import SessionLocal
from app.models.crop_cycle import CropCycle
from app.models.crop_stage_observation import CropStageObservation
from app.models.farm import Farm
from app.models.field import Field
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.models.season import Season
from app.models.user import User
from app.services.weather import WeatherProviderError


def _context(db):
    tag = str(uuid4())
    user = User(
        firebase_uid="radar-screen-" + tag,
        phone_e164="+91" + str(uuid4().int)[:10],
        preferred_language="en",
    )
    db.add(user)
    db.flush()
    farm = Farm(owner_user_id=user.id, name="Radar Screen Farm")
    db.add(farm)
    db.flush()
    field = Field(
        farm_id=farm.id, name="Rice Field",
        boundary=from_shape(
            Polygon([
                (76.70, 30.70), (76.71, 30.70), (76.71, 30.71),
                (76.70, 30.71), (76.70, 30.70),
            ]), srid=4326,
        ),
    )
    db.add(field)
    db.flush()
    season = Season(
        farm_id=farm.id, name="Kharif",
        started_on=date(2026, 6, 1), status="active",
    )
    db.add(season)
    db.flush()
    cycle = CropCycle(
        season_id=season.id,
        field_id=field.id,
        crop_name="rice",
        started_on=date(2026, 6, 1),
        planted_on=date(2026, 6, 15),
        status="active",
    )
    db.add(cycle)
    db.flush()
    db.add(CropStageObservation(
        crop_cycle_id=cycle.id,
        stage_code="vegetative",
        observed_on=date(2026, 8, 1),
    ))
    for acquired, vh in (
        (date(2026, 9, 10), -13.0),
        (date(2026, 9, 22), -13.2),
        (date(2026, 10, 4), -13.1),
        (date(2026, 10, 14), -18.5),
    ):
        scene = SatelliteObservation(
            field_id=field.id, observed_on=acquired,
            source="sentinel-1-rtc",
            scene_id="screen-test-" + str(uuid4()),
            metadata_json={
                "orbit_state": "ascending",
                "relative_orbit": 27,
                "platform": "sentinel-1d",
            },
        )
        db.add(scene)
        db.flush()
        db.add(SatelliteMetric(
            satellite_observation_id=scene.id,
            metric_type="sar_vh_db",
            raster_uri="gs://ci-farm-platform/testing/sar_vh.tif",
            median=vh, mean=vh,
            pixel_count=100, valid_pixel_count=100, valid_pixel_percent=100.0,
            metadata_json={},
        ))
    db.flush()
    return user, cycle


def test_owner_only_read_only_screening_survives_weather_outage(monkeypatch):
    db = SessionLocal()
    try:
        owner, cycle = _context(db)
        monkeypatch.setattr(
            "app.api.routes.radar_screening._today",
            lambda: date(2026, 10, 15),
        )
        def provider_offline(**kwargs):
            raise WeatherProviderError("Provider unavailable")

        monkeypatch.setattr(
            "app.api.routes.radar_screening.load_field_weather",
            provider_offline,
        )

        result = get_crop_radar_screening(
            crop_cycle_id=cycle.id,
            current_user=owner,
            db=db,
            as_of=date(2026, 10, 15),
        )
        assert result.orbits
        assert result.orbits[0].status == "review_variation"
        assert result.orbits[0].stage_source == "farmer_confirmed"
        assert result.orbits[0].weather.precipitation_3_day_mm is None
        assert any("Weather context unavailable" in x for x in result.warnings)

        with pytest.raises(HTTPException) as denied:
            get_crop_radar_screening(
                crop_cycle_id=cycle.id,
                current_user=User(id=uuid4()),
                db=db,
                as_of=date(2026, 10, 15),
            )
        assert denied.value.status_code == 404
    finally:
        db.rollback()
        db.close()
