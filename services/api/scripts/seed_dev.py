from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy import delete, or_, select

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


def harvest_details(
    *,
    yield_kg: float,
    harvested_area_acres: float,
    moisture_percent: float | None,
    quality_grade: str | None,
    selling_price_per_kg: float | None,
) -> dict:
    yield_per_acre = yield_kg / harvested_area_acres

    estimated_value = None

    if selling_price_per_kg is not None:
        estimated_value = yield_kg * selling_price_per_kg

    return {
        "yield_kg": yield_kg,
        "harvested_area_acres": harvested_area_acres,
        "yield_kg_per_acre": round(
            yield_per_acre,
            2,
        ),
        "moisture_percent": moisture_percent,
        "quality_grade": quality_grade,
        "selling_price_per_kg": selling_price_per_kg,
        "estimated_value": (
            round(
                estimated_value,
                2,
            )
            if estimated_value is not None
            else None
        ),
    }


# ============================================================
# EXACT FIELD BOUNDARIES FROM:
#
# Boundaries_08_21_2026 (1).geojson
#
# Original file stores each boundary as a MultiPolygon
# containing one Polygon.
#
# Our database currently stores POLYGON, so the single polygon
# ring from each feature is used directly.
# ============================================================

FIELD_DEFINITIONS = [
    {
        "id": UUID("f7807e24-002c-4898-a8d7-0f1137bf3e47"),
        "name": "khanpur 2",
        "variety": "PR-126",
        "started_on": date(2026, 6, 8),
        "planted_on": date(2026, 6, 16),
        "expected_harvest_on": date(2026, 10, 22),
        "coordinates": [
            (77.04943491038614, 29.93204033491577),
            (77.04944785588316, 29.93152650950367),
            (77.05008477822093, 29.93149285272301),
            (77.05009772383602, 29.930994731030097),
            (77.05064947608264, 29.930941930174413),
            (77.0506773991404, 29.93145010629462),
            (77.05097757249388, 29.9314634156525),
            (77.05103481487322, 29.93199457783001),
            (77.04942789581821, 29.932049637475473),
            (77.04943491038614, 29.93204033491577),
        ],
    },
    {
        "id": UUID("963b7a32-8922-44d7-a4bf-9bdb6edb0a73"),
        "name": "khanpur 3",
        "variety": "PR-126",
        "started_on": date(2026, 6, 9),
        "planted_on": date(2026, 6, 17),
        "expected_harvest_on": date(2026, 10, 24),
        "coordinates": [
            (77.0520079112161, 29.93302577178133),
            (77.05202072320094, 29.932583502049766),
            (77.05318341218924, 29.93254015861028),
            (77.05317487085358, 29.932682647450335),
            (77.05314284089968, 29.93277517255906),
            (77.05314711154472, 29.93290470759942),
            (77.05306703666628, 29.932964848817136),
            (77.05295920252462, 29.9330323919595),
            (77.05201431892891, 29.93304349493941),
            (77.0520079112161, 29.93302577178133),
        ],
    },
    {
        "id": UUID("a0f5997e-be8d-423e-8b8b-f2eeda369bf7"),
        "name": "Bee2",
        "variety": "PR-126",
        "started_on": date(2026, 6, 10),
        "planted_on": date(2026, 6, 18),
        "expected_harvest_on": date(2026, 10, 5),
        "coordinates": [
            (77.04956603608383, 29.926001090364167),
            (77.04967202634117, 29.92553936267457),
            (77.0478031789529, 29.92551991173265),
            (77.04778616746012, 29.926040577400528),
            (77.04952887020818, 29.926018209062462),
            (77.04956603608383, 29.926001090364167),
        ],
    },
    {
        "id": UUID("25582525-2bd2-4387-a8cb-a34d2d6df469"),
        "name": "santri tubewell",
        "variety": "Pusa-44",
        "started_on": date(2026, 6, 11),
        "planted_on": date(2026, 6, 19),
        "expected_harvest_on": date(2026, 11, 2),
        "coordinates": [
            (77.05729429928647, 29.91609848260758),
            (77.05731865772606, 29.91561570121509),
            (77.05733814447655, 29.91481481374433),
            (77.05807214537384, 29.91474584424634),
            (77.05839530070637, 29.915539694598408),
            (77.05839530070637, 29.915556584962403),
            (77.05785941505928, 29.91557910542319),
            (77.05784155217998, 29.91610129767406),
            (77.05726994084995, 29.916121003010034),
            (77.05729429928647, 29.91609848260758),
        ],
    },
    {
        "id": UUID("e3f19081-65af-4f55-9192-5be38d42aad7"),
        "name": "santri 2",
        "variety": "Pusa-44",
        "started_on": date(2026, 6, 12),
        "planted_on": date(2026, 6, 20),
        "expected_harvest_on": date(2026, 11, 5),
        "coordinates": [
            (77.05529850625885, 29.915620187567157),
            (77.05531748595729, 29.915085532395082),
            (77.05640502424444, 29.915059210863475),
            (77.0564847390952, 29.915138175514002),
            (77.05665365868089, 29.915159561737312),
            (77.05664986270875, 29.91557741523718),
            (77.05601973578081, 29.91559715630416),
            (77.05602353175658, 29.916105487397573),
            (77.05582044866128, 29.916108777583005),
            (77.05579197907122, 29.915620187567157),
            (77.05530420017828, 29.915644863887678),
            (77.05529850625885, 29.915620187567157),
        ],
    },
    {
        "id": UUID("406f67d0-ea2c-443c-8eac-fc54169eca57"),
        "name": "Rasulpur",
        "variety": "PR-126",
        "started_on": date(2026, 6, 13),
        "planted_on": date(2026, 6, 21),
        "expected_harvest_on": date(2026, 10, 28),
        "coordinates": [
            (77.05399487738754, 29.85847063710122),
            (77.05450216748062, 29.857208038655415),
            (77.05485163403523, 29.857201055255345),
            (77.05485646537085, 29.856878419671744),
            (77.05515761850938, 29.85684629570467),
            (77.05537663896939, 29.85728206313894),
            (77.05575248963771, 29.858434396661423),
            (77.05400509852143, 29.858462442909968),
            (77.05399487738754, 29.85847063710122),
        ],
    },
]


def main() -> None:
    db = SessionLocal()

    try:
        # =====================================================
        # USER
        # =====================================================

        user = db.scalar(
            select(User).where(
                or_(
                    User.firebase_uid == settings.dev_firebase_uid,
                    User.phone_e164 == settings.dev_phone_e164,
                )
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

        else:
            user.name = settings.dev_user_name

        print(f"Using dev user: " f"{user.name} ({user.id})")

        # =====================================================
        # DELETE PREVIOUS DEV FARM
        #
        # This will also delete:
        #
        # fields
        # crop cycles
        # activities
        # satellite observation DB rows
        #
        # via cascades.
        # =====================================================

        db.execute(delete(Farm).where(Farm.owner_user_id == user.id))

        db.flush()

        print("Deleted previous dev farm data.")

        # =====================================================
        # FARM
        # =====================================================

        farm = Farm(
            owner_user_id=user.id,
            name="Karnal Demo Farm",
            location_name="Haryana",
        )

        db.add(farm)
        db.flush()

        # =====================================================
        # REAL FIELD BOUNDARIES
        # =====================================================

        fields: dict[
            str,
            Field,
        ] = {}

        for definition in FIELD_DEFINITIONS:

            polygon = Polygon(definition["coordinates"])

            if not polygon.is_valid:
                raise RuntimeError("Invalid polygon for " f"{definition['name']}")

            field = Field(
                id=definition["id"],
                farm_id=farm.id,
                name=definition["name"],
                boundary=from_shape(
                    polygon,
                    srid=4326,
                ),
            )

            fields[definition["name"]] = field

            db.add(field)

        db.flush()

        # =====================================================
        # SEASON
        # =====================================================

        kharif_2026 = Season(
            farm_id=farm.id,
            name="Kharif 2026",
            season_type="kharif",
            status="active",
            started_on=date(
                2026,
                5,
                20,
            ),
            ended_on=None,
        )

        db.add(kharif_2026)

        db.flush()

        # =====================================================
        # CROP CYCLES
        # =====================================================

        crop_cycles: dict[
            str,
            CropCycle,
        ] = {}

        for definition in FIELD_DEFINITIONS:

            name = definition["name"]

            if name == "Bee2":

                crop_cycle = CropCycle(
                    season_id=kharif_2026.id,
                    field_id=fields[name].id,
                    crop_name="Rice",
                    variety=definition["variety"],
                    status="completed",
                    started_on=definition["started_on"],
                    planted_on=definition["planted_on"],
                    expected_harvest_on=definition["expected_harvest_on"],
                    harvested_on=date(
                        2026,
                        10,
                        8,
                    ),
                    yield_kg=6400.0,
                    harvested_area_acres=2.41,
                    moisture_percent=18.2,
                    quality_grade="Grade A",
                    selling_price_per_kg=23.50,
                    harvest_notes=(
                        "Good harvest. " "Minor uneven patch " "on one edge."
                    ),
                    notes="Seeded demo rice crop.",
                )

            else:

                crop_cycle = CropCycle(
                    season_id=kharif_2026.id,
                    field_id=fields[name].id,
                    crop_name="Rice",
                    variety=definition["variety"],
                    status="active",
                    started_on=definition["started_on"],
                    planted_on=definition["planted_on"],
                    expected_harvest_on=definition["expected_harvest_on"],
                    harvested_on=None,
                    yield_kg=None,
                    harvested_area_acres=None,
                    moisture_percent=None,
                    quality_grade=None,
                    selling_price_per_kg=None,
                    harvest_notes=None,
                    notes="Seeded demo rice crop.",
                )

            crop_cycles[name] = crop_cycle

            db.add(crop_cycle)

        db.flush()

        # =====================================================
        # ACTIVITY HELPER
        # =====================================================

        activities: list[Activity] = []

        def add_activity(
            *,
            field_name: str,
            activity_type: str,
            occurred_at: datetime,
            notes: str | None,
            details: dict,
            attach_to_crop: bool = True,
        ) -> None:

            activities.append(
                Activity(
                    field_id=fields[field_name].id,
                    crop_cycle_id=(
                        crop_cycles[field_name].id if attach_to_crop else None
                    ),
                    activity_type=activity_type,
                    occurred_at=occurred_at,
                    notes=notes,
                    details=details,
                )
            )

        # =====================================================
        # KHANPUR 2
        # =====================================================

        add_activity(
            field_name="khanpur 2",
            activity_type="tillage",
            occurred_at=dt(
                2026,
                6,
                8,
                7,
            ),
            notes="Laser levelling before rice crop.",
            details={
                "method": "laser_levelling",
                "tractor_hours": 2.4,
            },
            attach_to_crop=False,
        )

        add_activity(
            field_name="khanpur 2",
            activity_type="transplanting",
            occurred_at=dt(
                2026,
                6,
                16,
                6,
                30,
            ),
            notes="Rice transplanted.",
            details={
                "labour_count": 9,
            },
        )

        add_activity(
            field_name="khanpur 2",
            activity_type="irrigation",
            occurred_at=dt(
                2026,
                6,
                24,
                6,
            ),
            notes="Tubewell irrigation.",
            details={
                "duration_minutes": 260,
                "source": "tube_well",
            },
        )

        add_activity(
            field_name="khanpur 2",
            activity_type="fertilizer",
            occurred_at=dt(
                2026,
                7,
                2,
                8,
            ),
            notes=None,
            details={
                "product": "Urea",
                "quantity": 45,
                "unit": "kg_per_acre",
            },
        )

        add_activity(
            field_name="khanpur 2",
            activity_type="herbicide",
            occurred_at=dt(
                2026,
                7,
                11,
                6,
            ),
            notes="Weed control application.",
            details={
                "product": "Nominee Gold",
                "dose": 100,
                "dose_unit": "ml_per_acre",
            },
        )

        add_activity(
            field_name="khanpur 2",
            activity_type="incident",
            occurred_at=dt(
                2026,
                8,
                18,
                18,
            ),
            notes="Temporary waterlogging in lower patch.",
            details={
                "incident_type": "waterlogging",
                "severity": "moderate",
                "affected_area_percent": 14,
            },
        )

        # =====================================================
        # KHANPUR 3
        # =====================================================

        add_activity(
            field_name="khanpur 3",
            activity_type="transplanting",
            occurred_at=dt(
                2026,
                6,
                17,
                6,
            ),
            notes="Rice transplanted.",
            details={
                "labour_count": 6,
            },
        )

        add_activity(
            field_name="khanpur 3",
            activity_type="irrigation",
            occurred_at=dt(
                2026,
                6,
                25,
                7,
            ),
            notes="Irrigation.",
            details={
                "source": "tube_well",
                "duration_minutes": 180,
            },
        )

        add_activity(
            field_name="khanpur 3",
            activity_type="fertilizer",
            occurred_at=dt(
                2026,
                7,
                4,
                8,
            ),
            notes=None,
            details={
                "product": "Urea",
                "quantity": 42,
                "unit": "kg_per_acre",
            },
        )

        add_activity(
            field_name="khanpur 3",
            activity_type="pesticide",
            occurred_at=dt(
                2026,
                8,
                3,
                6,
            ),
            notes="Stem borer control.",
            details={
                "product": "Chlorantraniliprole",
                "target": "stem_borer",
            },
        )

        add_activity(
            field_name="khanpur 3",
            activity_type="observation",
            occurred_at=dt(
                2026,
                9,
                5,
                17,
            ),
            notes="Crop generally uniform.",
            details={
                "category": "crop_condition",
                "severity": "normal",
            },
        )

        # =====================================================
        # BEE2
        # =====================================================

        add_activity(
            field_name="Bee2",
            activity_type="transplanting",
            occurred_at=dt(
                2026,
                6,
                18,
                6,
            ),
            notes="Rice transplanted.",
            details={
                "labour_count": 8,
            },
        )

        add_activity(
            field_name="Bee2",
            activity_type="irrigation",
            occurred_at=dt(
                2026,
                6,
                27,
                7,
            ),
            notes=None,
            details={
                "source": "tube_well",
                "duration_minutes": 220,
            },
        )

        add_activity(
            field_name="Bee2",
            activity_type="fertilizer",
            occurred_at=dt(
                2026,
                7,
                6,
                8,
            ),
            notes=None,
            details={
                "product": "Urea",
                "quantity": 46,
                "unit": "kg_per_acre",
            },
        )

        add_activity(
            field_name="Bee2",
            activity_type="fungicide",
            occurred_at=dt(
                2026,
                8,
                22,
                6,
            ),
            notes="Preventive fungal spray.",
            details={
                "product": "Tricyclazole",
                "quantity": 120,
                "unit": "g_per_acre",
            },
        )

        add_activity(
            field_name="Bee2",
            activity_type="harvest",
            occurred_at=dt(
                2026,
                10,
                8,
                9,
            ),
            notes=crop_cycles["Bee2"].harvest_notes,
            details=harvest_details(
                yield_kg=6400.0,
                harvested_area_acres=2.41,
                moisture_percent=18.2,
                quality_grade="Grade A",
                selling_price_per_kg=23.50,
            ),
        )

        # =====================================================
        # SANTRI TUBEWELL
        # =====================================================

        add_activity(
            field_name="santri tubewell",
            activity_type="tillage",
            occurred_at=dt(
                2026,
                6,
                11,
                7,
            ),
            notes="Field preparation.",
            details={
                "method": "cultivator",
            },
            attach_to_crop=False,
        )

        add_activity(
            field_name="santri tubewell",
            activity_type="transplanting",
            occurred_at=dt(
                2026,
                6,
                19,
                6,
            ),
            notes="Pusa-44 transplanted.",
            details={
                "labour_count": 10,
            },
        )

        add_activity(
            field_name="santri tubewell",
            activity_type="irrigation",
            occurred_at=dt(
                2026,
                6,
                28,
                6,
            ),
            notes="Tubewell irrigation.",
            details={
                "source": "tube_well",
                "duration_minutes": 300,
            },
        )

        add_activity(
            field_name="santri tubewell",
            activity_type="weeding",
            occurred_at=dt(
                2026,
                7,
                28,
                7,
            ),
            notes="Manual weeding.",
            details={
                "method": "manual",
                "labour_count": 3,
            },
        )

        # =====================================================
        # SANTRI 2
        # =====================================================

        add_activity(
            field_name="santri 2",
            activity_type="transplanting",
            occurred_at=dt(
                2026,
                6,
                20,
                6,
            ),
            notes="Pusa-44 transplanted.",
            details={
                "labour_count": 9,
            },
        )

        add_activity(
            field_name="santri 2",
            activity_type="irrigation",
            occurred_at=dt(
                2026,
                6,
                29,
                7,
            ),
            notes=None,
            details={
                "source": "canal",
                "duration_minutes": 260,
            },
        )

        add_activity(
            field_name="santri 2",
            activity_type="fertilizer",
            occurred_at=dt(
                2026,
                7,
                8,
                7,
            ),
            notes=None,
            details={
                "product": "Urea",
                "quantity": 48,
                "unit": "kg_per_acre",
            },
        )

        add_activity(
            field_name="santri 2",
            activity_type="pesticide",
            occurred_at=dt(
                2026,
                8,
                6,
                6,
            ),
            notes="Insect control.",
            details={
                "target": "stem_borer",
            },
        )

        # =====================================================
        # RASULPUR
        #
        # Direct seeded rice example.
        # =====================================================

        add_activity(
            field_name="Rasulpur",
            activity_type="sowing",
            occurred_at=dt(
                2026,
                6,
                21,
                7,
            ),
            notes="Direct seeded rice.",
            details={
                "method": "direct_seeded",
                "seed_rate_kg_per_acre": 9,
            },
        )

        add_activity(
            field_name="Rasulpur",
            activity_type="irrigation",
            occurred_at=dt(
                2026,
                6,
                30,
                6,
            ),
            notes=None,
            details={
                "source": "tube_well",
                "duration_minutes": 360,
            },
        )

        add_activity(
            field_name="Rasulpur",
            activity_type="fertilizer",
            occurred_at=dt(
                2026,
                7,
                9,
                8,
            ),
            notes=None,
            details={
                "product": "Urea",
                "quantity": 44,
                "unit": "kg_per_acre",
            },
        )

        add_activity(
            field_name="Rasulpur",
            activity_type="herbicide",
            occurred_at=dt(
                2026,
                7,
                16,
                6,
            ),
            notes="Post-emergence weed control.",
            details={
                "product": "Bispyribac-sodium",
            },
        )

        add_activity(
            field_name="Rasulpur",
            activity_type="other",
            occurred_at=dt(
                2026,
                8,
                12,
                8,
            ),
            notes="Drainage channel cleaned.",
            details={
                "category": "field_maintenance",
                "work": "drainage_cleaning",
            },
        )

        # =====================================================
        # SAVE
        # =====================================================

        db.add_all(activities)

        db.commit()

        # =====================================================
        # OUTPUT
        # =====================================================

        print()
        print("========================================")

        print("Development database seeded successfully")

        print("========================================")

        print()
        print(f"Farm: {farm.name}")

        print()
        print("Imported fields:")

        for definition in FIELD_DEFINITIONS:

            field = fields[definition["name"]]

            cycle = crop_cycles[definition["name"]]

            print(f"  {field.name}: " f"{field.id} " f"[{cycle.status}]")

        print()
        print(
            "Activities:",
            len(activities),
        )

        activity_types = sorted({activity.activity_type for activity in activities})

        print()
        print("Activity types:")

        for activity_type in activity_types:
            print(f"  - {activity_type}")

        print()
        print("Satellite observations: 0")

        print("Run satellite-worker next " "to create REAL Sentinel-2 data.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
