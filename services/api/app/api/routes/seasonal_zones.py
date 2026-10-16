"""Explicit, user-triggered seasonal composite jobs; only aggregate grids persist."""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DBSession, CurrentUser
from app.models.crop_cycle import CropCycle
from app.models.field import Field
from app.models.seasonal_zone_composite import SeasonalZoneComposite
from app.services.ownership import get_owned_crop_cycle, get_owned_field
from app.services.weather import _today

router = APIRouter(tags=["manual historical seasonal zones"])

class CalculateRequest(BaseModel):
    crop_cycle_id: UUID
    years: list[int] = PydanticField(min_length=1, max_length=6)

def _template(db, current_user, field_id: UUID, crop_cycle_id: UUID):
    get_owned_field(db=db, user_id=current_user.id, field_id=field_id)
    cycle = get_owned_crop_cycle(db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id)
    if cycle.field_id != field_id:
        raise HTTPException(status_code=404, detail="Crop cycle is not on this field.")
    start = cycle.planted_on or cycle.started_on
    end = cycle.harvested_on or cycle.expected_harvest_on or start + timedelta(days=120)
    duration = (end - start).days
    if not 30 <= duration <= 240:
        raise HTTPException(status_code=422, detail="A 30–240 day growing-season window is required. Set a realistic planting and harvest window.")
    crop = " ".join(cycle.crop_name.strip().lower().split())
    # Same crop, same planting/harvest calendar is a comparable cohort.
    calendar_key = f"{start.month:02d}-{start.day:02d}-{duration:03d}"
    boundary = db.scalar(select(func.ST_AsEWKB(Field.boundary)).where(Field.id == field_id))
    if boundary is None:
        raise HTTPException(status_code=404, detail="Field boundary not found.")
    return cycle, start, duration, crop, calendar_key, hashlib.sha256(bytes(boundary)).hexdigest()

def _data(row, boundary_hash: str):
    return {
        "id": str(row.id), "year": row.year, "status": row.status if row.boundary_hash == boundary_hash else "stale_boundary",
        "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
        "season_label": row.season_label, "crop_key": row.crop_key,
        "error": row.error if row.boundary_hash == boundary_hash else "Field boundary has changed. Recalculate explicitly.",
        "result": row.result_json if row.boundary_hash == boundary_hash and row.status == "completed" else None,
    }

def _rows(db, field_id, crop, key):
    return list(db.scalars(select(SeasonalZoneComposite).where(
        SeasonalZoneComposite.field_id == field_id,
        SeasonalZoneComposite.crop_key == crop,
        SeasonalZoneComposite.calendar_key == key,
    ).order_by(SeasonalZoneComposite.year.desc())).all())

@router.get("/fields/{field_id}/seasonal-zones")
def list_seasonal_zones(
    field_id: UUID, crop_cycle_id: UUID, db: DBSession, current_user: CurrentUser,
) -> dict:
    cycle, start, duration, crop, key, hash_ = _template(db, current_user, field_id, crop_cycle_id)
    years = list(range(_today().year - 1, _today().year - 7, -1))
    return {
        "crop": crop, "crop_cycle_id": str(cycle.id), "field_id": str(field_id),
        "calendar_key": key, "reference_window": {
            "start": start.strftime("%d %b"), "length_days": duration,
            "basis": "Selected crop cycle calendar projected onto prior years; not verified historical sowing dates.",
        },
        "available_years": years,
        "seasons": [_data(r, hash_) for r in _rows(db, field_id, crop, key)],
    }

@router.post("/fields/{field_id}/seasonal-zones/calculate", status_code=202)
def calculate_seasonal_zones(
    field_id: UUID, request: CalculateRequest, db: DBSession, current_user: CurrentUser,
) -> dict:
    cycle, start, duration, crop, key, hash_ = _template(db, current_user, field_id, request.crop_cycle_id)
    years = sorted(set(request.years))
    allowed = set(range(_today().year - 6, _today().year))
    if not years or not set(years).issubset(allowed):
        raise HTTPException(status_code=422, detail="Choose one to six completed calendar years from the previous six years.")
    existing = {r.year: r for r in _rows(db, field_id, crop, key)}
    queued = []
    skipped = []
    for year in years:
        # Avoid 29 February template ambiguity.
        try:
            start_date = date(year, start.month, start.day)
        except ValueError:
            start_date = date(year, 2, 28)
        end_date = start_date + timedelta(days=duration)
        if end_date >= _today():
            raise HTTPException(status_code=422, detail="A selected growing season has not finished.")
        row = existing.get(year)
        if row is not None:
            if row.status in ("pending", "running") and row.boundary_hash == hash_:
                skipped.append(year)
                continue
            if row.status == "completed" and row.boundary_hash == hash_:
                skipped.append(year)
                continue
            row.result_json = None
            row.error = None
            row.started_at = None
            row.completed_at = None
            row.boundary_hash = hash_
            row.status = "pending"
            row.start_date, row.end_date = start_date, end_date
        else:
            row = SeasonalZoneComposite(
                field_id=field_id, crop_key=crop, calendar_key=key,
                season_label=f"{cycle.crop_name} {year}", year=year,
                start_date=start_date, end_date=end_date,
                boundary_hash=hash_, status="pending",
            )
            db.add(row)
        queued.append(year)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Another calculation was queued concurrently. Refresh.") from exc
    return {"queued_years": queued, "already_available_or_running": skipped, "worker_required": bool(queued)}

def _aggregate(rows, selected_years):
    """Equal weight to each year, never weight years by number of scenes."""
    selected = [r for r in rows if r.year in selected_years and r.status == "completed" and r.result_json]
    if len(selected) != len(selected_years):
        raise HTTPException(status_code=409, detail="All selected seasons must finish calculation first.")
    grids = [r.result_json for r in selected]
    base = grids[0]
    shape_key = (base["width"], base["height"], base["projection"], base["transform"], base["mask"])
    if any((g["width"], g["height"], g["projection"], g["transform"], g["mask"]) != shape_key for g in grids):
        raise HTTPException(status_code=409, detail="Saved seasons use incompatible grids. Recalculate using the same field boundary.")
    n = base["width"] * base["height"]
    pixels = []
    coverage = []
    for i in range(n):
        values = [g["pixels"][i] for g in grids if g["pixels"][i] is not None]
        # Require >=2 years and majority coverage when comparing multiple years.
        enough = len(values) >= (2 if len(grids) > 1 else 1) and len(values) >= (len(grids) + 1) // 2
        pixels.append(round(sum(values)/len(values), 4) if enough else None)
        coverage.append(len(values))
    good = [v for v in pixels if v is not None]
    average = round(sum(good)/len(good), 4) if good else None
    return {
        "width": base["width"], "height": base["height"], "mask": base["mask"],
        "pixels": pixels, "years_contributing": coverage, "mean_ndvi": average,
        "zone_threshold_ndvi": 0.08, "selected_years": sorted(selected_years),
        "zone_model": "relative_to_pooled_field_mean_v1",
        "notes": "Each year's season mean receives equal weight. Low zones mean NDVI at least 0.08 below the field-wide multi-year mean; not measured yield.",
    }

@router.post("/fields/{field_id}/seasonal-zones/combine")
def combine_seasonal_zones(
    field_id: UUID, request: CalculateRequest, db: DBSession, current_user: CurrentUser,
):
    _, _, _, crop, key, hash_ = _template(db, current_user, field_id, request.crop_cycle_id)
    years = sorted(set(request.years))
    if not 1 <= len(years) <= 6:
        raise HTTPException(status_code=422, detail="Select one to six years.")
    rows = [r for r in _rows(db, field_id, crop, key) if r.year in years and r.boundary_hash == hash_]
    return _aggregate(rows, years)
