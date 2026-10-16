"""Guardrails for temporal zone evidence and two-pass descriptive indices."""
from datetime import date
from uuid import uuid4

from shapely.geometry import box

from app.domains.satellite.spatial_history import Scene, summarize_spatial_history
from app.domains.satellite.field_intelligence import (
    build_field_comparisons, indices_for_stage,
)
from app.schemas.satellite_trends import SatelliteTrendPoint


def test_no_spatial_zones_without_three_usable_dates():
    geom = box(0, 0, 240, 240)
    scenes = [
        Scene(str(uuid4()), date(2026, 10, 1), 95, 20, {
            "below_field_baseline": box(0, 0, 120, 240),
        }),
        Scene(str(uuid4()), date(2026, 10, 8), 97, 20, {
            "below_field_baseline": box(0, 0, 120, 240),
        }),
    ]
    result = summarize_spatial_history(geom, 54000, scenes)
    assert result["status"] == "insufficient_history"
    assert result["zones"] == []
    assert result["tracking"] == []


def test_repeated_multi_year_low_zones_are_candidates_not_yield():
    geom = box(0, 0, 240, 240)
    dates = [
        date(2023, 8, 1), date(2023, 8, 9),
        date(2024, 8, 1), date(2024, 8, 9),
        date(2025, 8, 1), date(2025, 8, 9),
    ]
    scenes = [
        Scene(str(uuid4()), day, 99, 20, {
            "below_field_baseline": box(0, 0, 120, 240),
        })
        for day in dates
    ]
    result = summarize_spatial_history(geom, 54000, scenes)
    assert result["status"] == "candidate_zones"
    assert result["year_count"] == 3
    assert any(z["classification"] == "repeated_relative_low" for z in result["zones"])
    assert all("yield" in z["interpretation"] for z in result["zones"])
    assert any(z["transition"] == "persistent" for z in result["tracking"])


def test_short_history_tracks_anomalies_without_productivity_claims():
    geom = box(0, 0, 240, 240)
    days = [date(2026, 7, 1), date(2026, 7, 14), date(2026, 8, 1)]
    scenes = [
        Scene(str(uuid4()), day, 97, 20, {
            "below_field_baseline": box(0, 0, 120, 240)
            if i != 1 else box(80, 0, 240, 240),
        })
        for i, day in enumerate(days)
    ]
    result = summarize_spatial_history(geom, 54000, scenes)
    assert result["status"] == "short_history"
    assert not result["zones"]
    assert result["tracking"]


def test_incomplete_retrieval_suppresses_candidate_zones():
    geom = box(0, 0, 240, 240)
    scenes = [
        Scene(str(uuid4()), date(y, m, 1), 98, 20, {
            "below_field_baseline": box(0, 0, 100, 240),
        })
        for y in (2023, 2024, 2025) for m in (5, 6)
    ]
    result = summarize_spatial_history(geom, 54000, scenes, history_limited=True)
    assert result["zones"] == []
    assert result["tracking"] == []


def _point(day, metric, value, orbit, source="sentinel-1-rtc", coverage=97):
    return SatelliteTrendPoint(
        observation_id=uuid4(), observed_on=day, source=source,
        metric_type=metric, median=value, mean=value,
        valid_pixel_percent=coverage, orbit_state="ascending",
        relative_orbit=27, platform="sentinel-1a",
        radar_orbit_key=orbit, anomaly_zone_count=0, anomaly_area_acres=0,
    )


def test_two_pass_radar_is_same_orbit_and_requires_quality():
    points = [
        _point(date(2026, 10, 15), "sar_rvi", 0.71, "asc:27"),
        _point(date(2026, 10, 3), "sar_rvi", 0.51, "asc:27"),
        _point(date(2026, 10, 10), "sar_rvi", 1.19, "desc:78"),
        _point(date(2026, 9, 28), "sar_rvi", 0.81, "asc:27", coverage=25),
        _point(date(2026, 10, 15), "sar_rvi", 0.65, None),
    ]
    result = build_field_comparisons(points)
    pairs = [c for c in result["comparisons"] if c["orbit_key"] == "asc:27"]
    assert len(pairs) == 1
    assert pairs[0]["status"] == "complete"
    assert pairs[0]["change"] == 0.2
    assert pairs[0]["days_between"] == 12
    assert result["suppressed_unidentified_radar_metrics"] == 1
    other = [c for c in result["comparisons"] if c["orbit_key"] == "desc:78"]
    assert other[0]["status"] == "one_usable_date"


def test_unknown_crop_has_no_made_up_specific_index_advice():
    assert indices_for_stage("flowering", "other")["recommended_indices"] == []
    assert "soil" in indices_for_stage("planting", "rice")["guidance"].lower()
