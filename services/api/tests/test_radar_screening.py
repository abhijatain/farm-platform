"""Field-level screening deliberately requires matched orbit, stage and coverage."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.satellite_trends import (
    FieldSatelliteTrendsResponse,
    SatelliteTrendActivity,
    SatelliteTrendPoint,
)
from app.schemas.weather import WeatherDay
from app.services.radar_screening import (
    _weather_context,
    build_radar_screening,
    stage_at,
)


TODAY = date(2026, 10, 15)
CYCLE_ID = uuid4()
FIELD_ID = uuid4()
START = date(2026, 7, 1)


def recorded(code="vegetative", observed_on=START):
    return SimpleNamespace(
        stage_code=code,
        observed_on=observed_on,
    )


def point(
    observed_on, value,
    metric="sar_vh_db", *,
    orbit="ascending:27", coverage=100.0, scene_id=None,
):
    observation_id = scene_id or uuid4()
    orbit_state, relative = orbit.split(":") if orbit else (None, None)
    return SatelliteTrendPoint(
        observation_id=observation_id,
        observed_on=observed_on,
        source="sentinel-1-rtc",
        metric_type=metric,
        mean=value,
        median=value,
        valid_pixel_percent=coverage,
        orbit_state=orbit_state,
        relative_orbit=int(relative) if relative is not None else None,
        platform="sentinel-1d",
        radar_orbit_key=orbit,
        anomaly_zone_count=0,
        anomaly_area_acres=0,
    )


def make_trends(points, activities=None):
    return FieldSatelliteTrendsResponse(
        field_id=FIELD_ID,
        crop_cycle_id=CYCLE_ID,
        start_date=START,
        end_date=TODAY,
        metric_types=["sar_vh_db", "sar_vv_db", "sar_rvi", "ndvi"],
        points=points,
        activities=activities or [],
    )


def screen(
    points, *,
    crop_name="rice", confirmed=None, weather=None, activities=None, planted_on=START,
):
    return build_radar_screening(
        crop_cycle_id=CYCLE_ID,
        field_id=FIELD_ID,
        crop_name=crop_name,
        planted_on=planted_on,
        as_of=TODAY,
        stage_observations=confirmed if confirmed is not None else [recorded()],
        trends=make_trends(points, activities),
        weather_days=weather or [],
    )


def readings(values=(-13.0, -13.2, -12.9, -18.2), dates=None, orbit="ascending:27"):
    dates = dates or [
        date(2026, 9, 12),
        date(2026, 9, 24),
        date(2026, 10, 3),
        date(2026, 10, 14),
    ]
    return [point(day, value, orbit=orbit) for day, value in zip(dates, values)]


def test_same_stage_farmer_confirmed_three_baseline_passes_detect_unusual_variation():
    report = screen(readings())
    selected = report.orbits[0]
    assert selected.stage_code == "vegetative"
    assert selected.stage_source == "farmer_confirmed"
    assert selected.radar_orbit_key == "ascending:27"
    assert selected.status == "review_variation"
    metric = selected.metrics[0]
    assert metric.metric_type == "sar_vh_db"
    assert metric.baseline_passes == 3
    assert metric.status == "unusual_variation"
    assert metric.difference < -4
    assert metric.screening_threshold > 0
    assert "not a disease" in report.statement.lower()


def test_normal_radar_variation_stays_within_reference_range():
    report = screen(readings(values=(-13.0, -13.2, -12.9, -13.3)))
    assert report.orbits[0].status == "within_reference_range"


def test_an_unconfirmed_stage_never_triggers_flag_even_with_large_change():
    report = screen(readings(), confirmed=[])
    assert report.orbits[0].stage_source == "provisional"
    assert report.orbits[0].status == "insufficient_evidence"
    assert report.orbits[0].metrics[0].status == "unverified_stage"


def test_no_planting_date_and_no_stage_cannot_screen():
    report = screen(readings(), confirmed=[], planted_on=None)
    assert report.orbits[0].stage_source == "unknown"
    assert report.orbits[0].status == "insufficient_evidence"


def test_different_orbit_and_low_coverage_cannot_supply_baseline():
    points = [
        point(date(2026, 9, 12), -13, orbit="descending:136"),
        point(date(2026, 9, 24), -13, coverage=50),
        point(date(2026, 10, 3), -13),
        point(date(2026, 10, 14), -19),
    ]
    report = screen(points)
    ascending = next(x for x in report.orbits if x.radar_orbit_key == "ascending:27")
    assert ascending.metrics[0].status == "insufficient_baseline"
    assert ascending.metrics[0].baseline_passes == 1
    assert ascending.status == "insufficient_evidence"


def test_stage_transition_excludes_earlier_stage_from_baseline():
    recorded_stages = [
        recorded("vegetative", date(2026, 7, 1)),
        recorded("heading", date(2026, 10, 1)),
    ]
    report = screen(readings(), confirmed=recorded_stages)
    assert report.orbits[0].stage_code == "heading"
    assert report.orbits[0].metrics[0].baseline_passes == 1
    assert report.orbits[0].status == "insufficient_evidence"


def test_screening_uses_last_confirmed_transition_not_a_future_stage():
    stages = [
        recorded("vegetative", date(2026, 7, 1)),
        recorded("heading", date(2026, 11, 1)),
    ]
    assert stage_at(
        crop_name="rice", planted_on=START, as_of=TODAY, observations=stages,
    ) == ("vegetative", "farmer_confirmed")


def test_missing_orbit_geometry_is_excluded():
    points = readings()
    unknown = point(date(2026, 10, 15), -99, orbit=None)
    report = screen([*points, unknown])
    assert len(report.orbits) == 1
    assert report.orbits[0].observed_on == date(2026, 10, 14)


def test_three_day_rainfall_is_strict_and_moisture_is_context_only():
    days = [
        WeatherDay(date=TODAY - timedelta(days=n), source="historical", precipitation_mm=5)
        for n in range(3)
    ]
    # The first two days of context are omitted, not treated as dry.
    assert _weather_context(observed_on=TODAY, days=days[:2]).precipitation_3_day_mm is None
    report = screen(readings(), weather=[
        WeatherDay(
            date=date(2026, 10, 14) - timedelta(days=n),
            source="historical", precipitation_mm=5,
        ) for n in range(3)
    ])
    orbit = report.orbits[0]
    assert orbit.weather.precipitation_3_day_mm == 15
    assert orbit.weather.wet_weather_context is True
    assert orbit.status == "review_variation"
    assert any("moisture" in item for item in orbit.explanations)


def test_same_day_duplicate_passes_cannot_count_as_independent_baseline():
    r = readings()
    r.append(point(date(2026, 9, 24), -13, scene_id=uuid4()))
    report = screen(r)
    assert report.orbits[0].metrics[0].baseline_passes == 3


def test_recent_optical_and_crop_activity_are_context_not_diagnosis():
    latest = date(2026, 10, 14)
    optical = SatelliteTrendPoint(
        observation_id=uuid4(),
        observed_on=latest - timedelta(days=2),
        source="sentinel-2",
        metric_type="ndvi",
        mean=0.55,
        median=0.55,
        valid_pixel_percent=92,
        orbit_state=None,
        relative_orbit=None,
        platform=None,
        radar_orbit_key=None,
        anomaly_zone_count=0,
        anomaly_area_acres=0,
    )
    activity = SatelliteTrendActivity(
        id=uuid4(),
        occurred_at=datetime(2026, 10, 12, 10, tzinfo=timezone.utc),
        activity_type="irrigation",
        notes=None,
        crop_cycle_id=CYCLE_ID,
    )
    report = screen([*readings(), optical], activities=[activity])
    orbit = report.orbits[0]
    assert orbit.optical[0].metric_type == "ndvi"
    assert orbit.optical[0].days_from_radar == 2
    assert orbit.nearby_activities == ["irrigation"]
    assert orbit.status == "review_variation"
