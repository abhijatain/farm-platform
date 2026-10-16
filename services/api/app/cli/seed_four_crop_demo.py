"""Seed an EMPTY nonproduction Farm Platform DB from a local GeoJSON.

PLAN ONLY (no database or cloud access):
  uv run python -m app.cli.seed_four_crop_demo --geojson /path/field.geojson

Seed ONLY after a confirmed isolated test DB is empty:
  uv run python -m app.cli.seed_four_crop_demo --geojson /path/field.geojson \
    --firebase-uid '<UID_FROM_FIREBASE_CONSOLE>' \
    --phone '+91XXXXXXXXXX' --confirm-db-name 'actual_database_name' --apply

Never wipes other users, Firebase accounts, GCS objects or existing farms.
Never runs on API startup. Refuses production and nonempty databases.
Wheat and rice diary entries/yields are synthetic and labeled DEMO, while
queued Sentinel-2, Sentinel-1 and Landsat acquisitions are processed later
from the real STAC providers. No invented satellite metrics are stored.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from shapely.geometry import Polygon, shape

from app.cli.four_crop_demo_plan import (
    CROPS, activity_timestamp, plan_activities, satellite_date_windows,
    validate_demo_plan,
)


def load_field_polygon(path:Path) -> Polygon:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features",[])
        if len(features) != 1:
            raise ValueError("Demo requires exactly one field feature in the GeoJSON.")
        geometry = features[0].get("geometry")
    elif payload.get("type") == "Feature":
        geometry = payload.get("geometry")
    else:
        geometry = payload
    geom = shape(geometry)
    if geom.geom_type == "MultiPolygon":
        if len(geom.geoms) != 1:
            raise ValueError("Field has multiple disjoint polygons; this demo requires a single valid Polygon.")
        geom = geom.geoms[0]
    if not isinstance(geom,Polygon) or geom.is_empty or not geom.is_valid:
        raise ValueError("Expected one valid, non-empty Polygon boundary.")
    if not (-180 <= geom.bounds[0] <= geom.bounds[2] <= 180
            and -90 <= geom.bounds[1] <= geom.bounds[3] <= 90):
        raise ValueError("GeoJSON coordinates must use longitude/latitude in WGS84.")
    if geom.area <= 0:
        raise ValueError("Field has no measurable area.")
    return geom


def preview(geojson:Path) -> Polygon:
    validate_demo_plan()
    polygon = load_field_polygon(geojson)
    print("PLAN ONLY — no DB, GCS or Firebase write")
    print(f"Field polygon: valid, {len(polygon.exterior.coords)-1} vertices")
    print(f"Crop cycles: {len(CROPS)}; one farm, one physical field, four seasons")
    for crop in CROPS:
        rows=plan_activities(crop)
        print(f"  {crop.label}: {crop.started_on} -> planting {crop.planted_on} -> "
              f"harvest {crop.harvested_on}; {len(rows)} sample diary entries")
    print(f"Real-source satellite windows (queued, NOT fabricated): {len(satellite_date_windows())}")
    print("To seed: provide a verified Firebase UID/phone, exact nonproduction DB name and --apply.")
    return polygon


def seed(*,polygon:Polygon,firebase_uid:str,phone:str,confirm_db_name:str) -> None:
    from firebase_admin import auth
    from geoalchemy2.shape import from_shape
    from sqlalchemy import func,select
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    from app.core.firebase import get_firebase_app
    from app.db.session import SessionLocal
    from app.models.activity import Activity
    from app.models.crop_cycle import CropCycle
    from app.models.farm import Farm
    from app.models.field import Field
    from app.models.satellite_ingestion_job import SatelliteIngestionJob
    from app.models.season import Season
    from app.models.user import User

    environment = settings.environment.strip().lower()
    if environment not in {"development","test","testing","demo","staging"}:
        raise RuntimeError(f"Seeding refused in environment={environment!r}; use isolated nonproduction DB.")
    actual_name = make_url(settings.database_url).database
    if not actual_name or actual_name != confirm_db_name:
        raise RuntimeError("Exact DB-name confirmation required; refusing to write.")
    if not phone.startswith("+") or not phone[1:].isdigit():
        raise ValueError("Phone must be verified E.164, e.g. +91XXXXXXXXXX.")
    verified_user=auth.get_user(firebase_uid,app=get_firebase_app())
    if verified_user.phone_number != phone:
        raise RuntimeError("Firebase UID is not the user of the specified phone number. Aborting.")

    with SessionLocal() as db:
        # Refuse to overwrite any existing account, farm, field or pipeline data,
        # including unrelated users: full reset is a separate explicit operation.
        from app.models.media_asset import MediaAsset
        from app.models.satellite_observation import SatelliteObservation
        from app.models.satellite_metric import SatelliteMetric
        from app.models.seasonal_zone_composite import SeasonalZoneComposite
        from app.models.whatsapp_link import WhatsAppLink
        from app.models.whatsapp_inbound_event import WhatsAppInboundEvent
        from app.models.crop_stage_observation import CropStageObservation
        from app.models.satellite_anomaly import SatelliteAnomaly
        tables=(User,Farm,Field,Season,CropCycle,Activity,SatelliteIngestionJob,
                SatelliteObservation,SatelliteMetric,SeasonalZoneComposite,
                MediaAsset,WhatsAppLink,WhatsAppInboundEvent,CropStageObservation,
                SatelliteAnomaly)
        populated=[(model.__tablename__,db.scalar(select(func.count()).select_from(model)))
                   for model in tables]
        existing=[(name,n) for name,n in populated if n]
        if existing:
            raise RuntimeError(
                "Database NOT EMPTY; refusing seed without prior reviewed reset: "+str(existing)
            )

        owner=User(firebase_uid=firebase_uid,phone_e164=phone,
            name="Four-crop DEMO · synthetic activity diary",preferred_language="en")
        db.add(owner)
        db.flush()
        farm=Farm(owner_user_id=owner.id,name="One-field demonstration farm",
                  location_name="Demo boundary supplied by user")
        db.add(farm)
        db.flush()
        field=Field(farm_id=farm.id,name="Field 14253841",
                    boundary=from_shape(polygon,srid=4326))
        db.add(field)
        db.flush()
        area_m2=db.scalar(select(func.ST_Area(func.Geography(field.boundary))))  # PostGIS
        if area_m2 is None or area_m2 <= 0:
            raise RuntimeError("PostGIS did not return a valid field area")
        area_acres=float(area_m2)/4046.8564224

        for crop in CROPS:
            season=Season(farm_id=farm.id,name=crop.season_name,season_type=crop.season_type,
                          status="completed",started_on=crop.started_on,ended_on=crop.harvested_on)
            db.add(season)
            db.flush()
            # "Demo" embedded in the variety and narrative, never presented
            # as a farmer-measured original crop history.
            cycle=CropCycle(season_id=season.id,field_id=field.id,
                crop_name=crop.crop,variety=crop.variety,status="completed",
                started_on=crop.started_on,planted_on=crop.planted_on,
                expected_harvest_on=crop.harvested_on,
                harvested_on=crop.harvested_on,
                harvested_area_acres=round(area_acres,3),
                yield_kg=round(area_acres*crop.example_yield_kg_per_acre,1),
                harvest_notes="SYNTHETIC DEMO quantity. Not a measured yield, invoice or agronomic observation.",
                notes="DEMO ONLY: fictional farm activities and estimated yield for UI testing. "
                      "Satellite rasters are separate, real source acquisitions if ingestion succeeds.",
            )
            db.add(cycle)
            db.flush()
            for activity in plan_activities(crop):
                # Do not insert activities from the future. The 2026 rice
                # crop can have only the postharvest records already due.
                if activity.occurred_on > date.today():
                    continue
                db.add(Activity(field_id=field.id,crop_cycle_id=cycle.id,
                    activity_type=activity.activity_type,
                    occurred_at=activity_timestamp(activity.occurred_on),
                    notes=activity.notes+" [SYNTHETIC DEMO]",
                    details={
                        "demo":True,"fictitious":True,
                        "satellite_context_metrics":list(activity.satellite_metrics),
                        "satellite_readings_supplied":False,
                        "note":"Suggested viewable indices only; results must come from authentic STAC scenes.",
                    },
                ))
            # Queue one independent full multi-sensor historical window for
            # each crop; worker will process real optical/radar/thermal scenes.
            db.add(SatelliteIngestionJob(
                field_id=field.id,job_type="initial_backfill",
                start_date=crop.started_on,end_date=crop.harvested_on,
                status="pending",attempts=0,max_attempts=3,
                dedupe_key=f"four_crop_demo:{field.id}:{crop.crop}:{crop.harvested_on}",
            ))

        db.commit()
        print("SEED COMMITTED: 1 user, 1 farm, 1 field, 4 seasons, 4 crop cycles.")
        print("All diary/harvest values: SYNTHETIC DEMO. Satellite metrics: none inserted.")
        print("Queued 4 real-source multi-sensor backfill jobs; run satellite worker separately.")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geojson",type=Path,required=True,help="Local private GeoJSON; never commit user boundaries to a public repo")
    parser.add_argument("--firebase-uid",help="Firebase Auth UID for an already-existing test phone user")
    parser.add_argument("--phone",help="Verified E.164 number corresponding to the Firebase UID")
    parser.add_argument("--confirm-db-name",help="Exact nonproduction PostgreSQL DB name")
    parser.add_argument("--apply",action="store_true",help="Actually write to an EMPTY nonproduction DB")
    args=parser.parse_args()
    polygon=preview(args.geojson)
    if not args.apply: return
    if not (args.firebase_uid and args.phone and args.confirm_db_name):
        parser.error("--apply requires --firebase-uid, --phone and --confirm-db-name")
    seed(polygon=polygon,firebase_uid=args.firebase_uid,phone=args.phone,
         confirm_db_name=args.confirm_db_name)


if __name__=="__main__":
    main()
