"""Field preparation → planting → growth plan → independent historical windows.

These tests use PostGIS, exercise owner boundaries, and do not invoke STAC
or schedule satellite ingestion. Historical calculation remains manual.
"""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.activities import create_activity
from app.api.routes.crop_cycles import update_crop_cycle_plan
from app.api.routes.seasonal_zones import (
    CalculateRequest, calculate_seasonal_zones,
    list_saved_zone_windows, list_seasonal_zones,
)
from app.db.session import SessionLocal
from app.models.activity import Activity
from app.models.seasonal_zone_composite import SeasonalZoneComposite
from app.models.user import User
from app.schemas.activity import ActivityCreate
from app.schemas.crop_cycle import CropCyclePlanUpdate
from test_field_intelligence_routes import _create_fixture


def test_tractor_preparation_then_sowing_sets_local_planting_date():
    db = SessionLocal()
    user = None
    try:
        user, field, cycle = _create_fixture(db)
        cycle.planted_on = None
        cycle.started_on = date(2026, 9, 1)
        db.commit()
        tractor = create_activity(
            field_id=field.id,
            data=ActivityCreate(
                crop_cycle_id=cycle.id,
                activity_type="tillage",
                occurred_at=datetime.fromisoformat("2026-09-01T07:00:00+05:30"),
                notes="Tractor preparation", details={},
            ),
            db=db, current_user=user,
        )
        assert tractor.crop_cycle_id == cycle.id
        assert cycle.planted_on is None

        sowing = create_activity(
            field_id=field.id,
            data=ActivityCreate(
                crop_cycle_id=cycle.id,
                activity_type="sowing",
                # 00:30 IST is the *previous day* in UTC. Preserve local day.
                occurred_at=datetime.fromisoformat("2026-09-08T00:30:00+05:30"),
                notes="Rice planted", details={},
            ),
            db=db, current_user=user,
        )
        db.refresh(cycle)
        assert cycle.planted_on == date(2026, 9, 8)
        assert sowing.occurred_at is not None
        assert len(db.scalars(select(Activity).where(Activity.crop_cycle_id == cycle.id)).all()) == 2

        with pytest.raises(HTTPException) as duplicate:
            create_activity(
                field.id,
                ActivityCreate(
                    crop_cycle_id=cycle.id,
                    activity_type="transplanting",
                    occurred_at=datetime.fromisoformat("2026-09-10T10:00:00+05:30"),
                ),
                db, user,
            )
        assert duplicate.value.status_code == 409

        corrected = update_crop_cycle_plan(
            cycle.id,
            CropCyclePlanUpdate(expected_harvest_on=date(2026, 12, 1)),
            db, user,
        )
        assert corrected.planted_on == date(2026, 9, 8)
        assert corrected.expected_harvest_on == date(2026, 12, 1)

        with pytest.raises(HTTPException) as invalid:
            update_crop_cycle_plan(
                cycle.id,
                CropCyclePlanUpdate(expected_harvest_on=date(2026, 8, 30)),
                db, user,
            )
        assert invalid.value.status_code == 422

        with pytest.raises(HTTPException) as denied:
            update_crop_cycle_plan(
                cycle.id, CropCyclePlanUpdate(expected_harvest_on=None),
                db, User(id=uuid4()),
            )
        assert denied.value.status_code == 404
    finally:
        if user is not None:
            db.delete(user)
            db.commit()
        else:
            db.rollback()
        db.close()


def test_independent_monthly_history_windows_never_enqueue_automatically(monkeypatch):
    import app.api.routes.seasonal_zones as seasonal

    monkeypatch.setattr(seasonal, "_today", lambda: date(2026, 10, 16))
    db = SessionLocal()
    user = None
    try:
        user, field, cycle = _create_fixture(db)
        august = list_seasonal_zones(
            field.id, cycle.id, db, user, start_month=8, end_month=10,
        )
        assert august["seasons"] == []
        assert august["calendar_key"] == "month-08-to-10"
        assert august["reference_window"]["length_days"] == 91

        payload = CalculateRequest(
            crop_cycle_id=cycle.id, years=[2024,2025],
            start_month=8, end_month=10,
        )
        queued = calculate_seasonal_zones(field.id, payload, db, user)
        assert queued["queued_years"] == [2024,2025]
        rows = list(db.scalars(select(SeasonalZoneComposite).where(
            SeasonalZoneComposite.field_id == field.id,
        )).all())
        assert {row.calendar_key for row in rows} == {"month-08-to-10"}
        assert all(row.status == "pending" and row.result_json is None for row in rows)
        assert all(row.window_source == "user_selected_months" for row in rows)
        assert {(row.year,row.start_date,row.end_date) for row in rows} == {
            (2024,date(2024,8,1),date(2024,10,31)),
            (2025,date(2025,8,1),date(2025,10,31)),
        }

        # Second report uses a different temporal scope, not a duplicate cycle.
        winter = calculate_seasonal_zones(field.id, CalculateRequest(
            crop_cycle_id=cycle.id, years=[2024],
            start_month=11, end_month=1,
        ), db, user)
        assert winter["queued_years"] == [2024]
        winter_row = db.scalar(select(SeasonalZoneComposite).where(
            SeasonalZoneComposite.field_id == field.id,
            SeasonalZoneComposite.calendar_key == "month-11-to-01",
        ))
        assert winter_row.start_date == date(2024,11,1)
        assert winter_row.end_date == date(2025,1,31)

        # Opening a saved window fetches the exact stored report, even when
        # the currently selected month controls refer to another period.
        historical = list_seasonal_zones(
            field.id, cycle.id, db, user,
            start_month=8, end_month=10,
            saved_calendar_key="month-11-to-01",
        )
        assert historical["calendar_key"] == "month-11-to-01"
        assert historical["reference_window"]["length_days"] == 91
        assert [r["year"] for r in historical["seasons"]] == [2024]
        with pytest.raises(HTTPException) as missing:
            list_seasonal_zones(
                field.id, cycle.id, db, user,
                start_month=8, end_month=10,
                saved_calendar_key="month-09-to-11",
            )
        assert missing.value.status_code == 404
        with pytest.raises(HTTPException) as incomplete:
            seasonal.combine_seasonal_zones(
                field.id,
                seasonal.CombineRequest(
                    crop_cycle_id=cycle.id, years=[2024],
                    start_month=8, end_month=10,
                    saved_calendar_key="month-11-to-01",
                ),
                db, user,
            )
        assert incomplete.value.status_code == 409

        saved = list_saved_zone_windows(field.id, cycle.id, db, user)
        assert {item["calendar_key"] for item in saved} == {
            "month-08-to-10", "month-11-to-01",
        }
        assert all(item["completed_years"] == [] for item in saved)
        repeat = calculate_seasonal_zones(field.id,payload,db,user)
        assert repeat["queued_years"] == []
        assert repeat["already_available_or_running"] == [2024,2025]

        with pytest.raises(HTTPException) as denied:
            list_seasonal_zones(
                field.id, cycle.id, db, User(id=uuid4()),
                start_month=8,end_month=10,
            )
        assert denied.value.status_code == 404
    finally:
        if user is not None:
            db.delete(user)
            db.commit()
        else:
            db.rollback()
        db.close()



def test_two_crop_cycles_in_one_field_and_same_season():
    from app.api.routes.crop_cycles import create_crop_cycle, list_field_crop_cycles
    from app.schemas.crop_cycle import CropCycleCreate

    db = SessionLocal()
    user = None
    try:
        user, field, rice = _create_fixture(db)
        maize = create_crop_cycle(
            rice.season_id,
            CropCycleCreate(
                field_id=field.id,
                crop_name="maize",
                started_on=date(2026, 10, 11),
                planted_on=None,
                expected_harvest_on=None,
            ),
            db,
            user,
        )
        assert maize.id != rice.id
        assert maize.season_id == rice.season_id
        assert maize.field_id == rice.field_id
        assert {row.id for row in list_field_crop_cycles(field.id, db, user)} >= {rice.id, maize.id}
    finally:
        if user is not None:
            db.delete(user)
            db.commit()
        else:
            db.rollback()
        db.close()


def test_completed_cycle_accepts_past_corrections_and_postharvest_sales():
    db = SessionLocal()
    user = None
    try:
        user, field, cycle = _create_fixture(db)
        cycle.harvested_on = date(2026, 10, 8)
        cycle.status = "completed"
        db.commit()

        past_work = create_activity(
            field.id, ActivityCreate(
                crop_cycle_id=cycle.id, activity_type="tillage",
                occurred_at=datetime.fromisoformat("2026-06-02T10:00:00+05:30"),
                notes="Recorded retrospectively",
            ), db, user,
        )
        drying = create_activity(
            field.id, ActivityCreate(
                crop_cycle_id=cycle.id, activity_type="drying",
                occurred_at=datetime.fromisoformat("2026-10-09T09:00:00+05:30"),
                notes="Post-harvest drying",
            ), db, user,
        )
        assert past_work.id != drying.id
        with pytest.raises(HTTPException) as wrong_cycle:
            create_activity(
                field.id, ActivityCreate(
                    crop_cycle_id=cycle.id, activity_type="irrigation",
                    occurred_at=datetime.fromisoformat("2026-10-12T11:00:00+05:30"),
                ), db, user,
            )
        assert wrong_cycle.value.status_code == 409
    finally:
        if user is not None:
            db.delete(user)
            db.commit()
        else:
            db.rollback()
        db.close()


def test_field_wide_months_are_not_mislabeled_as_rice_seasons(monkeypatch):
    import app.api.routes.seasonal_zones as zones

    monkeypatch.setattr(zones, "_today", lambda: date(2026, 10, 16))
    db = SessionLocal()
    user = None
    try:
        user, field, cycle = _create_fixture(db)
        rice = CalculateRequest(crop_cycle_id=cycle.id, years=[2024],start_month=8,end_month=10)
        all_crops = CalculateRequest(crop_cycle_id=cycle.id, years=[2024],start_month=8,end_month=10,all_crops=True)
        zones.calculate_seasonal_zones(field.id, rice, db, user)
        zones.calculate_seasonal_zones(field.id, all_crops, db, user)
        rows = list(db.scalars(select(SeasonalZoneComposite).where(
            SeasonalZoneComposite.field_id == field.id,
        )).all())
        assert len(rows) == 2
        assert {row.crop_key for row in rows} == {"rice", "__all_crops__"}
        assert zones.list_seasonal_zones(
            field.id, cycle.id, db, user, 8, 10, True,
        )["crop"] == "field history (all crops)"
        assert zones.list_saved_zone_windows(field.id,cycle.id,db,user,True)[0]["calendar_key"] == "month-08-to-10"
        with pytest.raises(HTTPException) as invalid:
            zones.list_seasonal_zones(field.id,cycle.id,db,user,all_crops=True)
        assert invalid.value.status_code == 422
    finally:
        if user is not None:
            db.delete(user)
            db.commit()
        else:
            db.rollback()
        db.close()
