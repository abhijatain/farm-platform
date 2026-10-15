from datetime import date
from uuid import uuid4

from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon

from app.db.session import SessionLocal
from app.models.farm import Farm
from app.models.field import Field
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.models.user import User
from app.services.satellite_change import (
    build_field_satellite_change,
    default_pixel_change_threshold,
)


def _field(db) -> Field:
    unique = str(
        uuid4()
    )

    user = User(
        firebase_uid=(
            "change-test-"
            + unique
        ),
        phone_e164=(
            "+91"
            + str(
                uuid4().int
            )[:10]
        ),
        name="Change Test",
        preferred_language="en",
    )

    db.add(
        user
    )
    db.flush()

    farm = Farm(
        owner_user_id=user.id,
        name=(
            "Change Test Farm "
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
            "Change Test Field "
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

    return field


def _add_metric(
    db,
    *,
    field_id,
    observed_on: date,
    metric_type: str,
    median: float,
    valid_percent: float = 100.0,
    orbit_state: str | None = None,
    relative_orbit: int | None = None,
    platform: str | None = None,
) -> None:
    observation = (
        SatelliteObservation(
            field_id=field_id,
            observed_on=(
                observed_on
            ),
            source=(
                "sentinel-1-rtc"
                if metric_type.startswith(
                    "sar_"
                )
                else (
                    "landsat-c2-l2"
                    if metric_type
                    == "lst_c"
                    else "sentinel-2"
                )
            ),
            scene_id=(
                f"{metric_type}-"
                f"{observed_on.isoformat()}-"
                f"{uuid4()}"
            ),
            cloud_cover_percent=5.0,
            metadata_json={
                "processing_status":
                    "metrics_processed",
                **(
                    {
                        "orbit_state":
                            orbit_state,
                        "relative_orbit":
                            relative_orbit,
                        "platform":
                            platform,
                    }
                    if metric_type.startswith(
                        "sar_"
                    )
                    else {}
                ),
            },
        )
    )

    db.add(
        observation
    )
    db.flush()

    db.add(
        SatelliteMetric(
            satellite_observation_id=(
                observation.id
            ),
            metric_type=(
                metric_type
            ),
            raster_uri=(
                "gs://ci-farm-platform/"
                "users/u/farms/f/fields/x/"
                f"dates/{observed_on.isoformat()}/"
                f"{metric_type}.tif"
            ),
            mean=median,
            median=median,
            min=median - 0.1,
            max=median + 0.1,
            std=0.03,
            native_resolution_m=10.0,
            output_resolution_m=10.0,
            pixel_count=100,
            valid_pixel_count=int(
                valid_percent
            ),
            valid_pixel_percent=(
                valid_percent
            ),
            metadata_json={},
        )
    )

    db.flush()


def test_previous_change_uses_immediately_previous_usable_date() -> None:
    db = SessionLocal()

    try:
        field = _field(
            db
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                20,
            ),
            metric_type="ndvi",
            median=0.40,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                2,
            ),
            metric_type="ndvi",
            median=0.55,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            metric_type="ndvi",
            median=0.67,
        )

        result = (
            build_field_satellite_change(
                db=db,
                field_id=field.id,
                metric_type="ndvi",
                mode="previous",
                requested_to_date=None,
                requested_from_date=None,
                crop_cycle_id=None,
                crop_reference_date=None,
                minimum_valid_percent=80.0,
                date_tolerance_days=7,
                pixel_change_threshold=None,
            )
        )

        assert (
            result.status
            == "complete"
        )

        assert result.before is not None
        assert result.after is not None

        assert (
            result.before.observed_on
            == date(
                2026,
                10,
                2,
            )
        )

        assert (
            result.after.observed_on
            == date(
                2026,
                10,
                5,
            )
        )

        assert (
            result.scalar
            .days_between
            == 3
        )

        assert (
            round(
                result.scalar
                .median_change
                or 0.0,
                3,
            )
            == 0.12
        )

    finally:
        db.rollback()
        db.close()


def test_fourteen_day_mode_resolves_nearest_real_acquisition() -> None:
    db = SessionLocal()

    try:
        field = _field(
            db
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                20,
            ),
            metric_type="ndmi",
            median=0.18,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                23,
            ),
            metric_type="ndmi",
            median=0.22,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            metric_type="ndmi",
            median=0.31,
        )

        result = (
            build_field_satellite_change(
                db=db,
                field_id=field.id,
                metric_type="ndmi",
                mode="days_14",
                requested_to_date=None,
                requested_from_date=None,
                crop_cycle_id=None,
                crop_reference_date=None,
                minimum_valid_percent=80.0,
                date_tolerance_days=4,
                pixel_change_threshold=None,
            )
        )

        assert result.before is not None
        assert result.after is not None

        assert (
            result.baseline_target_date
            == date(
                2026,
                9,
                21,
            )
        )

        assert (
            result.before.observed_on
            == date(
                2026,
                9,
                20,
            )
        )

        assert (
            result.after.observed_on
            == date(
                2026,
                10,
                5,
            )
        )

    finally:
        db.rollback()
        db.close()


def test_low_coverage_baseline_is_not_selected() -> None:
    db = SessionLocal()

    try:
        field = _field(
            db
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                1,
            ),
            metric_type="ndvi",
            median=0.70,
            valid_percent=30.0,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                25,
            ),
            metric_type="ndvi",
            median=0.48,
            valid_percent=95.0,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            metric_type="ndvi",
            median=0.64,
            valid_percent=98.0,
        )

        result = (
            build_field_satellite_change(
                db=db,
                field_id=field.id,
                metric_type="ndvi",
                mode="previous",
                requested_to_date=None,
                requested_from_date=None,
                crop_cycle_id=None,
                crop_reference_date=None,
                minimum_valid_percent=80.0,
                date_tolerance_days=7,
                pixel_change_threshold=None,
            )
        )

        assert result.before is not None

        assert (
            result.before.observed_on
            == date(
                2026,
                9,
                25,
            )
        )

    finally:
        db.rollback()
        db.close()


def test_lst_change_does_not_report_percentage_change() -> None:
    db = SessionLocal()

    try:
        field = _field(
            db
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                28,
            ),
            metric_type="lst_c",
            median=30.0,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            metric_type="lst_c",
            median=33.0,
        )

        result = (
            build_field_satellite_change(
                db=db,
                field_id=field.id,
                metric_type="lst_c",
                mode="previous",
                requested_to_date=None,
                requested_from_date=None,
                crop_cycle_id=None,
                crop_reference_date=None,
                minimum_valid_percent=80.0,
                date_tolerance_days=7,
                pixel_change_threshold=None,
            )
        )

        assert (
            result.scalar
            .median_change
            == 3.0
        )

        assert (
            result.scalar
            .median_percent_change
            is None
        )

        assert (
            result.pixel_change_threshold
            == 1.0
        )

    finally:
        db.rollback()
        db.close()


def test_default_change_thresholds_are_metric_aware() -> None:
    assert (
        default_pixel_change_threshold(
            "ndvi"
        )
        == 0.03
    )

    assert (
        default_pixel_change_threshold(
            "sar_vv_db"
        )
        == 1.0
    )

    assert (
        default_pixel_change_threshold(
            "lst_c"
        )
        == 1.0
    )



def test_sar_change_skips_more_recent_mismatched_orbit() -> None:
    db = SessionLocal()

    try:
        field = _field(
            db
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                20,
            ),
            metric_type="sar_rvi",
            median=0.60,
            orbit_state="descending",
            relative_orbit=63,
            platform="sentinel-1a",
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                9,
                28,
            ),
            metric_type="sar_rvi",
            median=1.05,
            orbit_state="ascending",
            relative_orbit=136,
            platform="sentinel-1a",
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                10,
                5,
            ),
            metric_type="sar_rvi",
            median=0.82,
            orbit_state="descending",
            relative_orbit=63,
            platform="sentinel-1a",
        )

        result = (
            build_field_satellite_change(
                db=db,
                field_id=field.id,
                metric_type="sar_rvi",
                mode="previous",
                requested_to_date=None,
                requested_from_date=None,
                crop_cycle_id=None,
                crop_reference_date=None,
                minimum_valid_percent=80.0,
                date_tolerance_days=14,
                pixel_change_threshold=None,
            )
        )

        assert result.before is not None
        assert result.after is not None

        assert (
            result.before.observed_on
            == date(
                2026,
                9,
                20,
            )
        )

        assert (
            result.after.observed_on
            == date(
                2026,
                10,
                5,
            )
        )

        assert (
            result.before.orbit_state
            == "descending"
        )

        assert (
            result.after.orbit_state
            == "descending"
        )

        assert (
            result.before.relative_orbit
            == 63
        )

        assert (
            result.after.relative_orbit
            == 63
        )

        assert (
            result.anomalies
            .persistence_basis
            == "radar_anomaly_rules_not_enabled"
        )

        assert (
            result.anomalies
            .persistent_area_acres
            is None
        )

    finally:
        db.rollback()
        db.close()


def test_sar_change_missing_orbit_geometry_never_guesses_baseline() -> None:
    db = SessionLocal()

    try:
        for orbit_state, relative_orbit in (
            ("descending", None),
            (None, 63),
            (None, None),
        ):
            field = _field(db)

            _add_metric(
                db,
                field_id=field.id,
                observed_on=date(2026, 9, 28),
                metric_type="sar_rvi",
                median=0.45,
                orbit_state="ascending",
                relative_orbit=136,
            )

            _add_metric(
                db,
                field_id=field.id,
                observed_on=date(2026, 10, 5),
                metric_type="sar_rvi",
                median=0.82,
                orbit_state=orbit_state,
                relative_orbit=relative_orbit,
            )

            for mode in ("previous", "days_7"):
                result = build_field_satellite_change(
                    db=db,
                    field_id=field.id,
                    metric_type="sar_rvi",
                    mode=mode,
                    requested_to_date=None,
                    requested_from_date=None,
                    crop_cycle_id=None,
                    crop_reference_date=None,
                    minimum_valid_percent=80.0,
                    date_tolerance_days=7,
                    pixel_change_threshold=None,
                )

                assert result.after is not None
                assert result.before is None
                assert result.status == "missing_baseline"

    finally:
        db.rollback()
        db.close()
