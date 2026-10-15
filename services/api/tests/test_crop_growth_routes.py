"""DB-backed stage record, edit and delete regression coverage."""
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy import select

from app.api.routes.crop_growth import (
    delete_growth_stage,
    record_growth_stage,
)
from app.db.session import SessionLocal
from app.models.crop_cycle import CropCycle
from app.models.crop_stage_observation import CropStageObservation
from app.models.farm import Farm
from app.models.field import Field
from app.models.season import Season
from app.models.user import User
from app.schemas.crop_growth import StageObservationInput


def _context(db):
    tag = str(uuid4())
    user = User(
        firebase_uid="growth-test-" + tag,
        phone_e164="+91" + str(uuid4().int)[:10],
        preferred_language="en",
    )
    db.add(user)
    db.flush()
    farm = Farm(owner_user_id=user.id, name="Growth Farm " + tag[:7])
    db.add(farm)
    db.flush()
    field = Field(
        farm_id=farm.id, name="Wheat Field",
        boundary=from_shape(Polygon([
            (76.70, 30.70), (76.71, 30.70), (76.71, 30.71),
            (76.70, 30.71), (76.70, 30.70),
        ]), srid=4326),
    )
    db.add(field)
    db.flush()
    season = Season(farm_id=farm.id, name="Test Growth Season", started_on=date(2026, 9, 1), status="active")
    db.add(season)
    db.flush()
    cycle = CropCycle(
        season_id=season.id, field_id=field.id,
        crop_name="wheat", status="active",
        started_on=date(2026, 9, 5), planted_on=date(2026, 9, 8),
    )
    db.add(cycle)
    db.flush()
    return user, cycle


def test_record_update_remove_growth_stages(monkeypatch):
    db = SessionLocal()
    try:
        user, cycle = _context(db)
        monkeypatch.setattr("app.api.routes.crop_growth._today", lambda: date(2026, 10, 15))
        record_growth_stage(
            crop_cycle_id=cycle.id,
            data=StageObservationInput(stage_code="emergence", observed_on=date(2026, 9, 17)),
            db=db,
            current_user=user,
        )
        record_growth_stage(
            crop_cycle_id=cycle.id,
            data=StageObservationInput(stage_code="vegetative", observed_on=date(2026, 10, 4)),
            db=db,
            current_user=user,
        )
        updated = record_growth_stage(
            crop_cycle_id=cycle.id,
            data=StageObservationInput(stage_code="emergence", observed_on=date(2026, 9, 18), notes="Verified"),
            db=db,
            current_user=user,
        )
        assert updated.notes == "Verified"
        assert len(db.scalars(select(CropStageObservation).where(CropStageObservation.crop_cycle_id == cycle.id)).all()) == 2

        with pytest.raises(HTTPException) as error:
            record_growth_stage(
                crop_cycle_id=cycle.id,
                data=StageObservationInput(stage_code="heading", observed_on=date(2026, 9, 10)),
                db=db,
                current_user=user,
            )
        assert error.value.status_code == 409

        with pytest.raises(HTTPException) as error:
            record_growth_stage(
                crop_cycle_id=cycle.id,
                data=StageObservationInput(stage_code="maturity", observed_on=date(2026, 11, 10)),
                db=db,
                current_user=user,
            )
        assert error.value.status_code == 422

        delete_growth_stage(crop_cycle_id=cycle.id, stage_code="vegetative", db=db, current_user=user)
        assert len(db.scalars(select(CropStageObservation).where(CropStageObservation.crop_cycle_id == cycle.id)).all()) == 1

        intruder = User(id=uuid4())
        with pytest.raises(HTTPException) as error:
            record_growth_stage(
                crop_cycle_id=cycle.id,
                data=StageObservationInput(stage_code="heading", observed_on=date(2026, 10, 10)),
                db=db,
                current_user=intruder,
            )
        assert error.value.status_code == 404
    finally:
        # Explicit cleanup needed because the handlers commit their changes.
        if "user" in locals():
            db.delete(user)
            db.commit()
        db.close()
