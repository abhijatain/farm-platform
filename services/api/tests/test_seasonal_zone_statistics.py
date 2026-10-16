"""Non-stored NDVI color contrast must not fabricate agronomic zone evidence."""
import pytest

from app.domains.satellite.seasonal_zone_statistics import (
    combine_deviations, describe_zone_grid,
)


def grid(values):
    return {
        "width": 4, "height": 4,
        "projection": "EPSG:32643",
        "transform": [10.0, 0, 0, 0, -10.0, 0],
        "mask": [True] * 16,
        "pixels": values,
    }


def test_uniform_field_uses_soft_color_but_suppresses_spurious_zones():
    result = describe_zone_grid(grid([0.498] * 16))
    assert result["status"] == "low_spatial_contrast"
    assert result["zones"]["low_area_acres"] == 0
    assert result["zones"]["high_area_acres"] == 0
    assert result["zones"]["medium_percent"] == 100
    assert result["display"]["max"] - result["display"]["min"] >= 0.06 - 1e-4


def test_real_spatial_variation_produces_low_medium_high_counts():
    values = [0.3] * 5 + [0.5] * 6 + [0.7] * 5
    result = describe_zone_grid(grid(values))
    assert result["status"] == "zones_available"
    assert result["zone_classes"].count("low") == 5
    assert result["zone_classes"].count("medium") == 6
    assert result["zone_classes"].count("high") == 5
    assert result["zones"]["low_percent"] == 31.2
    assert result["zones"]["high_percent"] == 31.2


def test_combined_field_centering_ignores_whole_season_baseline_shifts():
    base = [0.35] * 8 + [0.65] * 8
    years = [grid(base), grid([x + 0.12 for x in base]), grid([x - 0.10 for x in base])]
    relative, n, stable = combine_deviations(years, years[0]["mask"])
    assert n == [3] * 16
    assert relative[:8] == pytest.approx([-0.15] * 8)
    assert relative[8:] == pytest.approx([0.15] * 8)
    assert stable == [True] * 16
    analyzed = describe_zone_grid(years[0], relative_pixels=relative)
    assert analyzed["status"] == "zones_available"
    assert analyzed["zones"]["low_percent"] == 50
    assert analyzed["zones"]["high_percent"] == 50


def test_two_years_do_not_claim_temporal_stability():
    a, b = grid([0.4] * 8 + [0.6] * 8), grid([0.45] * 8 + [0.65] * 8)
    relative, counts, stable = combine_deviations([a,b], a["mask"])
    assert all(x is not None for x in relative)
    assert counts == [2] * 16
    assert stable == [None] * 16


def test_single_season_combines_without_erasing_valid_cells():
    a = grid([0.4] * 8 + [0.6] * 8)
    relative, counts, stable = combine_deviations([a], a["mask"])
    assert relative[0] == pytest.approx(-0.1)
    assert relative[-1] == pytest.approx(0.1)
    assert counts == [1] * 16
    assert stable == [None] * 16
