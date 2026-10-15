"""Check radar orbit segmentation and optical trend generation."""

from datetime import date, datetime, timezone
from uuid import uuid4

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Polygon

from app.db.session import SessionLocal
from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.farm import Farm
from app.models.field import Field
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.models.season import Season
from app.models.user import User
from app.domains.satellite.trends import (
    TREND_METRIC_TYPES,
    get_field_satellite_trends,
)


def _build_context(db):
    unique = str(
        uuid4()
    )

    user = User(
        firebase_uid=(
            "trend-test-"
            + unique
        ),
        phone_e164=(
            "+91"
            + str(
                uuid4().int
            )[:10]
        ),
        name="Trend Test",
        preferred_language="en",
    )

    db.add(
        user
    )
    db.flush()

    farm = Farm(
        owner_user_id=user.id,
        name=(
            "Trend Test Farm "
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
            "Trend Test Field "
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

    season = Season(
        farm_id=farm.id,
        name=(
            "Kharif "
            + unique[:6]
        ),
        season_type="kharif",
        status="active",
        started_on=date(
            2026,
            6,
            1,
        ),
        ended_on=None,
    )

    db.add(
        season
    )
    db.flush()

    crop_cycle = CropCycle(
        season_id=season.id,
        field_id=field.id,
        crop_name="Rice",
        variety="PR-126",
        status="completed",
        started_on=date(
            2026,
            6,
            10,
        ),
        planted_on=date(
            2026,
            6,
            15,
        ),
        expected_harvest_on=date(
            2026,
            10,
            10,
        ),
        harvested_on=date(
            2026,
            10,
            5,
        ),
        notes=None,
    )

    db.add(
        crop_cycle
    )
    db.flush()

    return (
        field,
        crop_cycle,
    )


def _add_metric(
    db,
    *,
    field_id,
    observed_on: date,
    metric_type: str,
    median: float,
    valid_percent: float,
):
    source = (
        "sentinel-1-rtc"
        if metric_type
        == "sar_rvi"
        else (
            "landsat-c2-l2"
            if metric_type
            == "lst_c"
            else "sentinel-2"
        )
    )

    observation = SatelliteObservation(
        field_id=field_id,
        observed_on=observed_on,
        source=source,
        scene_id=(
            f"{metric_type}-"
            f"{observed_on.isoformat()}-"
            f"{uuid4()}"
        ),
        cloud_cover_percent=5.0,
        metadata_json={
            "processing_status":
                "metrics_processed",
        },
    )

    db.add(
        observation
    )
    db.flush()

    metric = SatelliteMetric(
        satellite_observation_id=(
            observation.id
        ),
        metric_type=metric_type,
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

    db.add(
        metric
    )
    db.flush()

    return (
        observation,
        metric,
    )


def _add_radar_pass(
    db,
    *,
    field_id,
    observed_on: date,
    orbit_state: str,
    relative_orbit: int,
    platform: str,
):
    observation = SatelliteObservation(
        field_id=field_id,
        observed_on=observed_on,
        source="sentinel-1-rtc",
        scene_id=(
            "radar-"
            f"{observed_on.isoformat()}-"
            f"{uuid4()}"
        ),
        cloud_cover_percent=None,
        metadata_json={
            "processing_status":
                "metrics_processed",
            "orbit_state":
                orbit_state,
            "relative_orbit":
                relative_orbit,
            "platform":
                platform,
        },
    )

    db.add(
        observation
    )
    db.flush()

    values = {
        "sar_vv_db":
            -8.5,
        "sar_vh_db":
            -13.2,
        "sar_vv_vh_ratio":
            2.95,
        "sar_rvi":
            0.91,
    }

    for (
        metric_type,
        median,
    ) in values.items():
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
                valid_pixel_count=100,
                valid_pixel_percent=100.0,
                metadata_json={},
            )
        )

    db.flush()

    return observation


def _add_anomaly(
    db,
    *,
    observation_id,
    metric_type: str,
    zone_index: int,
    area_acres: float,
):
    area_sqm = (
        area_acres
        * 4046.8564224
    )

    polygon = Polygon(
        [
            (76.700, 30.700),
            (76.702, 30.700),
            (76.702, 30.702),
            (76.700, 30.702),
            (76.700, 30.700),
        ]
    )

    db.add(
        SatelliteAnomaly(
            satellite_observation_id=(
                observation_id
            ),
            index_type=(
                metric_type
            ),
            zone_index=(
                zone_index
            ),
            anomaly_type=(
                "below_field_baseline"
            ),
            severity="moderate",
            geometry=from_shape(
                MultiPolygon(
                    [
                        polygon
                    ]
                ),
                srid=4326,
            ),
            pixel_count=10,
            area_sqm=area_sqm,
            area_acres=area_acres,
            zone_mean_value=0.3,
            zone_min_value=0.2,
            zone_max_value=0.4,
            field_mean_value=0.5,
            field_median_value=0.5,
            threshold_value=0.35,
            difference_from_field=-0.2,
            percent_difference=-40.0,
            detection_method=(
                "robust_mad_metric_v1"
            ),
            metadata_json={},
        )
    )

    db.flush()


def test_trends_share_crop_window_metrics_anomalies_and_activities() -> None:
    db = SessionLocal()

    try:
        (
            field,
            crop_cycle,
        ) = _build_context(
            db
        )

        before_crop, _ = (
            _add_metric(
                db,
                field_id=field.id,
                observed_on=date(
                    2026,
                    6,
                    10,
                ),
                metric_type="ndvi",
                median=0.20,
                valid_percent=99.0,
            )
        )

        optical, _ = (
            _add_metric(
                db,
                field_id=field.id,
                observed_on=date(
                    2026,
                    7,
                    1,
                ),
                metric_type="ndvi",
                median=0.48,
                valid_percent=92.0,
            )
        )

        _add_anomaly(
            db,
            observation_id=(
                optical.id
            ),
            metric_type="ndvi",
            zone_index=0,
            area_acres=0.20,
        )

        _add_anomaly(
            db,
            observation_id=(
                optical.id
            ),
            metric_type="ndvi",
            zone_index=1,
            area_acres=0.15,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                7,
                1,
            ),
            metric_type="ndmi",
            median=0.31,
            valid_percent=88.0,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                7,
                2,
            ),
            metric_type="sar_rvi",
            median=0.72,
            valid_percent=100.0,
        )

        _add_metric(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                7,
                5,
            ),
            metric_type="lst_c",
            median=33.2,
            valid_percent=96.0,
        )

        db.add(
            Activity(
                field_id=field.id,
                crop_cycle_id=(
                    crop_cycle.id
                ),
                activity_type=(
                    "irrigation"
                ),
                occurred_at=(
                    datetime(
                        2026,
                        7,
                        3,
                        8,
                        30,
                        tzinfo=(
                            timezone.utc
                        ),
                    )
                ),
                notes=(
                    "Canal irrigation"
                ),
                details={},
            )
        )

        db.flush()

        result = (
            get_field_satellite_trends(
                db=db,
                field_id=field.id,
                crop_cycle=(
                    crop_cycle
                ),
                start_date=None,
                end_date=None,
            )
        )

        assert (
            result.start_date
            == date(
                2026,
                6,
                15,
            )
        )

        assert (
            result.end_date
            == date(
                2026,
                10,
                5,
            )
        )

        assert (
            result.metric_types
            == list(
                TREND_METRIC_TYPES
            )
        )

        assert all(
            point.observed_on
            >= result.start_date
            for point
            in result.points
        )

        assert not any(
            point.observation_id
            == before_crop.id
            for point
            in result.points
        )

        ndvi = next(
            point
            for point
            in result.points
            if point.metric_type
            == "ndvi"
        )

        assert (
            ndvi.median
            == 0.48
        )

        assert (
            ndvi.valid_pixel_percent
            == 92.0
        )

        assert (
            ndvi.anomaly_zone_count
            == 2
        )

        assert (
            round(
                ndvi.anomaly_area_acres,
                2,
            )
            == 0.35
        )

        assert {
            point.metric_type
            for point
            in result.points
        } == {
            "ndvi",
            "ndmi",
            "sar_rvi",
            "lst_c",
        }

        assert (
            len(
                result.activities
            )
            == 1
        )

        assert (
            result.activities[
                0
            ].activity_type
            == "irrigation"
        )

    finally:
        db.rollback()
        db.close()


def test_explicit_window_overrides_crop_cycle_window() -> None:
    db = SessionLocal()

    try:
        (
            field,
            crop_cycle,
        ) = _build_context(
            db
        )

        result = (
            get_field_satellite_trends(
                db=db,
                field_id=field.id,
                crop_cycle=(
                    crop_cycle
                ),
                start_date=date(
                    2026,
                    8,
                    1,
                ),
                end_date=date(
                    2026,
                    8,
                    31,
                ),
            )
        )

        assert (
            result.start_date
            == date(
                2026,
                8,
                1,
            )
        )

        assert (
            result.end_date
            == date(
                2026,
                8,
                31,
            )
        )

    finally:
        db.rollback()
        db.close()



def test_radar_trends_expose_all_metrics_and_orbit_geometry() -> None:
    db = SessionLocal()

    try:
        (
            field,
            crop_cycle,
        ) = _build_context(
            db
        )

        radar = _add_radar_pass(
            db,
            field_id=field.id,
            observed_on=date(
                2026,
                7,
                20,
            ),
            orbit_state="descending",
            relative_orbit=63,
            platform="sentinel-1a",
        )

        result = (
            get_field_satellite_trends(
                db=db,
                field_id=field.id,
                crop_cycle=(
                    crop_cycle
                ),
                start_date=None,
                end_date=None,
            )
        )

        radar_points = [
            point
            for point
            in result.points
            if point.observation_id
            == radar.id
        ]

        assert {
            point.metric_type
            for point
            in radar_points
        } == {
            "sar_vv_db",
            "sar_vh_db",
            "sar_vv_vh_ratio",
            "sar_rvi",
        }

        assert all(
            point.orbit_state
            == "descending"
            for point
            in radar_points
        )

        assert all(
            point.relative_orbit
            == 63
            for point
            in radar_points
        )

        assert all(
            point.platform
            == "sentinel-1a"
            for point
            in radar_points
        )

        assert all(
            point.radar_orbit_key
            == "descending:63"
            for point
            in radar_points
        )

    finally:
        db.rollback()
        db.close()


def test_partial_radar_geometry_does_not_create_comparison_group() -> None:
    from app.domains.satellite.trends import _radar_metadata

    for metadata in (
        {"orbit_state": "descending"},
        {"relative_orbit": 63},
        {},
    ):
        _, _, _, orbit_key = _radar_metadata(
            source="sentinel-1-rtc",
            metadata_json=metadata,
        )

        assert orbit_key is None
