from datetime import date, datetime
from zoneinfo import ZoneInfo

from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import SessionLocal

from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.farm import Farm
from app.models.field import Field
from app.models.season import Season
from app.models.user import User


IST = ZoneInfo("Asia/Kolkata")


def dt(
    year: int,
    month: int,
    day: int,
    hour: int = 8,
    minute: int = 0,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=IST,
    )


def main() -> None:
    db = SessionLocal()

    try:
        # -----------------------------------------------------
        # DEV USER
        # -----------------------------------------------------
        user = db.scalar(
            select(User).where(
                User.firebase_uid == settings.dev_firebase_uid
            )
        )

        if user is None:
            user = User(
                firebase_uid=settings.dev_firebase_uid,
                phone_e164=settings.dev_phone_e164,
                name=settings.dev_user_name,
                preferred_language="en",
            )

            db.add(user)
            db.flush()

        print(f"Using dev user: {user.name} ({user.id})")

        # -----------------------------------------------------
        # REMOVE OLD TEST FARM DATA
        # -----------------------------------------------------
        # Activities/fields/seasons/crop cycles will disappear
        # through the database's ON DELETE CASCADE relationships.
        db.execute(
            delete(Farm).where(
                Farm.owner_user_id == user.id
            )
        )

        db.flush()

        print("Deleted previous dev farm data.")

        # -----------------------------------------------------
        # FARM
        # -----------------------------------------------------
        farm = Farm(
            owner_user_id=user.id,
            name="Karnal Test Farm",
            location_name="Karnal, Haryana",
        )

        db.add(farm)
        db.flush()

        # -----------------------------------------------------
        # FIELDS
        #
        # These are fake test polygons near Karnal.
        # GeoJSON/PostGIS coordinates use:
        #
        #     longitude, latitude
        #
        # -----------------------------------------------------

        field_1_polygon = Polygon(
            [
                (76.9900, 29.6850),
                (76.9920, 29.6850),
                (76.9920, 29.6870),
                (76.9900, 29.6870),
                (76.9900, 29.6850),
            ]
        )

        field_2_polygon = Polygon(
            [
                (76.9930, 29.6850),
                (76.9950, 29.6850),
                (76.9950, 29.6870),
                (76.9930, 29.6870),
                (76.9930, 29.6850),
            ]
        )

        field_3_polygon = Polygon(
            [
                (76.9900, 29.6880),
                (76.9922, 29.6880),
                (76.9922, 29.6900),
                (76.9900, 29.6900),
                (76.9900, 29.6880),
            ]
        )

        field_1 = Field(
            farm_id=farm.id,
            name="Tubewell Field",
            boundary=from_shape(
                field_1_polygon,
                srid=4326,
            ),
        )

        field_2 = Field(
            farm_id=farm.id,
            name="Road Field",
            boundary=from_shape(
                field_2_polygon,
                srid=4326,
            ),
        )

        field_3 = Field(
            farm_id=farm.id,
            name="Mango Side Field",
            boundary=from_shape(
                field_3_polygon,
                srid=4326,
            ),
        )

        db.add_all(
            [
                field_1,
                field_2,
                field_3,
            ]
        )

        db.flush()

        # -----------------------------------------------------
        # SEASON
        # -----------------------------------------------------
        season = Season(
            farm_id=farm.id,
            name="Kharif 2027",
            season_type="kharif",
            status="active",
            started_on=date(2027, 5, 15),
            ended_on=None,
        )

        db.add(season)
        db.flush()

        # -----------------------------------------------------
        # CROP CYCLES
        #
        # Same season, but different fields can grow completely
        # different crops / varieties.
        # -----------------------------------------------------

        paddy_pr126 = CropCycle(
            season_id=season.id,
            field_id=field_1.id,
            crop_name="Paddy",
            variety="PR-126",
            status="active",
            started_on=date(2027, 6, 10),
            planted_on=date(2027, 6, 18),
            expected_harvest_on=date(2027, 10, 20),
            harvested_on=None,
            notes="Direct test crop cycle for Tubewell Field.",
        )

        paddy_pusa44 = CropCycle(
            season_id=season.id,
            field_id=field_2.id,
            crop_name="Paddy",
            variety="Pusa-44",
            status="active",
            started_on=date(2027, 6, 12),
            planted_on=date(2027, 6, 20),
            expected_harvest_on=date(2027, 11, 5),
            harvested_on=None,
            notes="Second paddy field with different variety.",
        )

        maize = CropCycle(
            season_id=season.id,
            field_id=field_3.id,
            crop_name="Maize",
            variety="HQPM-1",
            status="active",
            started_on=date(2027, 6, 5),
            planted_on=date(2027, 6, 8),
            expected_harvest_on=date(2027, 9, 25),
            harvested_on=None,
            notes="Test maize crop cycle.",
        )

        db.add_all(
            [
                paddy_pr126,
                paddy_pusa44,
                maize,
            ]
        )

        db.flush()

        # -----------------------------------------------------
        # FIELD 1 ACTIVITIES
        # Paddy PR-126
        # -----------------------------------------------------

        field_1_activities = [
            Activity(
                field_id=field_1.id,
                crop_cycle_id=None,
                activity_type="tillage",
                occurred_at=dt(2027, 6, 10, 7, 0),
                notes="Laser levelling before transplanting.",
                details={
                    "method": "laser_levelling",
                    "tractor_hours": 2.5,
                },
            ),
            Activity(
                field_id=field_1.id,
                crop_cycle_id=paddy_pr126.id,
                activity_type="transplanting",
                occurred_at=dt(2027, 6, 18, 6, 30),
                notes="Paddy transplanted.",
                details={
                    "labour_count": 8,
                },
            ),
            Activity(
                field_id=field_1.id,
                crop_cycle_id=paddy_pr126.id,
                activity_type="irrigation",
                occurred_at=dt(2027, 7, 4, 7, 30),
                notes="Tubewell irrigation.",
                details={
                    "duration_minutes": 240,
                    "source": "tube_well",
                },
            ),
            Activity(
                field_id=field_1.id,
                crop_cycle_id=paddy_pr126.id,
                activity_type="fertilizer",
                occurred_at=dt(2027, 7, 10, 8, 15),
                notes=None,
                details={
                    "product": "Urea",
                    "quantity": 45,
                    "unit": "kg_per_acre",
                },
            ),
            Activity(
                field_id=field_1.id,
                crop_cycle_id=paddy_pr126.id,
                activity_type="herbicide",
                occurred_at=dt(2027, 7, 19, 6, 30),
                notes="Weed control application.",
                details={
                    "product": "Nominee Gold",
                    "dose": 100,
                    "dose_unit": "ml_per_acre",
                },
            ),
            Activity(
                field_id=field_1.id,
                crop_cycle_id=paddy_pr126.id,
                activity_type="irrigation",
                occurred_at=dt(2027, 7, 25, 7, 0),
                notes=None,
                details={
                    "duration_minutes": 210,
                    "source": "tube_well",
                },
            ),
        ]

        # -----------------------------------------------------
        # FIELD 2 ACTIVITIES
        #
        # Same general crop type, different field schedule.
        # -----------------------------------------------------

        field_2_activities = [
            Activity(
                field_id=field_2.id,
                crop_cycle_id=paddy_pusa44.id,
                activity_type="transplanting",
                occurred_at=dt(2027, 6, 20, 6, 0),
                notes=None,
                details={},
            ),
            Activity(
                field_id=field_2.id,
                crop_cycle_id=paddy_pusa44.id,
                activity_type="irrigation",
                occurred_at=dt(2027, 7, 6, 6, 30),
                notes="Canal irrigation.",
                details={
                    "duration_minutes": 300,
                    "source": "canal",
                },
            ),
            Activity(
                field_id=field_2.id,
                crop_cycle_id=paddy_pusa44.id,
                activity_type="fertilizer",
                occurred_at=dt(2027, 7, 13, 7, 45),
                notes=None,
                details={
                    "product": "Urea",
                    "quantity": 50,
                    "unit": "kg_per_acre",
                },
            ),
            Activity(
                field_id=field_2.id,
                crop_cycle_id=paddy_pusa44.id,
                activity_type="pesticide",
                occurred_at=dt(2027, 8, 1, 6, 15),
                notes="Preventive spray.",
                details={
                    "product": "Test pesticide",
                    "quantity": 250,
                    "unit": "ml_per_acre",
                },
            ),
        ]

        # -----------------------------------------------------
        # FIELD 3 ACTIVITIES
        # Maize
        # -----------------------------------------------------

        field_3_activities = [
            Activity(
                field_id=field_3.id,
                crop_cycle_id=maize.id,
                activity_type="sowing",
                occurred_at=dt(2027, 6, 8, 7, 0),
                notes="Maize sowing.",
                details={
                    "method": "seed_drill",
                },
            ),
            Activity(
                field_id=field_3.id,
                crop_cycle_id=maize.id,
                activity_type="irrigation",
                occurred_at=dt(2027, 6, 15, 7, 15),
                notes=None,
                details={
                    "duration_minutes": 180,
                    "source": "tube_well",
                },
            ),
            Activity(
                field_id=field_3.id,
                crop_cycle_id=maize.id,
                activity_type="fertilizer",
                occurred_at=dt(2027, 6, 25, 8, 0),
                notes=None,
                details={
                    "product": "DAP",
                    "quantity": 30,
                    "unit": "kg_per_acre",
                },
            ),
            Activity(
                field_id=field_3.id,
                crop_cycle_id=maize.id,
                activity_type="observation",
                occurred_at=dt(2027, 7, 20, 17, 30),
                notes="Farmer noticed some yellowing.",
                details={
                    "category": "crop_condition",
                    "severity": "mild",
                    "description": "Yellow leaves in north-west part.",
                },
            ),
        ]

        db.add_all(
            field_1_activities
            + field_2_activities
            + field_3_activities
        )

        db.commit()

        # -----------------------------------------------------
        # OUTPUT
        # -----------------------------------------------------

        print()
        print("========================================")
        print("Development database seeded successfully")
        print("========================================")
        print()

        print(f"User:   {user.id}")
        print(f"Farm:   {farm.id}")
        print(f"Season: {season.id}")

        print()
        print("Fields:")
        print(f"  Tubewell Field:   {field_1.id}")
        print(f"  Road Field:       {field_2.id}")
        print(f"  Mango Side Field: {field_3.id}")

        print()
        print("Crop cycles:")
        print(f"  PR-126:  {paddy_pr126.id}")
        print(f"  Pusa-44: {paddy_pusa44.id}")
        print(f"  Maize:   {maize.id}")

        print()
        print(
            "Activities created:",
            len(
                field_1_activities
                + field_2_activities
                + field_3_activities
            ),
        )

        print()
        print("Try:")
        print(
            f"GET /api/v1/fields/{field_1.id}/timeline"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
