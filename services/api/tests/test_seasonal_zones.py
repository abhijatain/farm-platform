"""Manual season job idempotence, field ownership and equal-year aggregation."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.api.routes import seasonal_zones
from app.api.routes.seasonal_zones import CalculateRequest, _aggregate
from app.db.session import SessionLocal
from app.models.seasonal_zone_composite import SeasonalZoneComposite
from app.models.user import User
from test_field_intelligence_routes import _create_fixture


def _grid(pixels):
    return {
        "width": 2, "height": 2, "projection": "EPSG:32643",
        "transform": [20.0, 0.0, 0.0, 0.0, -20.0, 0.0],
        "mask": [True, True, True, True],
        "pixels": pixels,
        "mean_ndvi": 0.5,
        "scene_count": 4,
    }


def test_equal_year_weights_not_scene_counts():
    a = type("Record", (), {
        "year": 2024, "status": "completed", "result_json": _grid([0.3,0.7,None,0.5]),
    })()
    b = type("Record", (), {
        "year": 2025, "status": "completed", "result_json": _grid([0.7,0.7,0.2,0.5]),
    })()
    out = _aggregate([a,b],[2024,2025])
    assert out["pixels"] == [0.5,0.7,None,0.5]
    assert out["years_contributing"] == [2,2,1,2]
    assert out["mean_ndvi"] == pytest.approx((0.5+0.7+0.5)/3)


def test_incompatible_saved_grids_are_rejected():
    a = type("Record", (), {"year":2024,"status":"completed","result_json":_grid([0.3]*4)})()
    bgrid = _grid([0.7]*4)
    bgrid["projection"] = "EPSG:32644"
    b = type("Record", (), {"year":2025,"status":"completed","result_json":bgrid})()
    with pytest.raises(HTTPException) as exc:
        _aggregate([a,b],[2024,2025])
    assert exc.value.status_code == 409


def test_manual_enqueue_no_duplicate_and_owner_only(monkeypatch):
    monkeypatch.setattr(seasonal_zones, "_today", lambda: date(2026,10,16))
    db=SessionLocal()
    user=None
    try:
        user, field, cycle = _create_fixture(db)
        payload=CalculateRequest(crop_cycle_id=cycle.id, years=[2023,2024])
        first=seasonal_zones.calculate_seasonal_zones(field.id,payload,db,user)
        assert first["queued_years"] == [2023,2024]
        rows=list(db.scalars(select(SeasonalZoneComposite).where(SeasonalZoneComposite.field_id==field.id)).all())
        assert len(rows)==2
        assert all(r.status=="pending" and r.result_json is None for r in rows)
        second=seasonal_zones.calculate_seasonal_zones(field.id,payload,db,user)
        assert second["queued_years"]==[]
        assert second["already_available_or_running"]==[2023,2024]
        assert len(db.scalars(select(SeasonalZoneComposite).where(SeasonalZoneComposite.field_id==field.id)).all())==2

        with pytest.raises(HTTPException) as denied:
            seasonal_zones.calculate_seasonal_zones(
                field.id,payload,db,User(id=uuid4())
            )
        assert denied.value.status_code==404
    finally:
        if user is not None:
            db.delete(user)
            db.commit()
        else:
            db.rollback()
        db.close()
