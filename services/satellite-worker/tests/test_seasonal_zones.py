"""Unit tests for ephemeral seasonal processing and scene sampling."""
from datetime import datetime, date, timezone
from types import SimpleNamespace

from satellite_worker.ingestion.seasonal_zones import (
    canonical_grid, select_scenes, MAX_DIM,
)

def _item(day: int, cloud: int):
    return SimpleNamespace(
        id=f"scene-{day}-{cloud}",
        datetime=datetime(2025, 7, day, tzinfo=timezone.utc),
        properties={"eo:cloud_cover": cloud},
    )

def test_prefers_low_cloud_and_different_temporal_bins():
    scenes = [_item(1,60), _item(4,0), _item(5,45), _item(15,12), _item(25,30)]
    selected = select_scenes(scenes, date(2025,7,1))
    assert [i.id for i in selected] == ["scene-4-0","scene-15-12","scene-25-30"]

def test_single_small_field_grid_is_bounded_and_shape_aware():
    polygon = {
        "type":"Polygon",
        "coordinates":[[
            [76.700,30.700],[76.708,30.700],[76.708,30.702],
            [76.700,30.702],[76.700,30.700],
        ]],
    }
    _, _, mask = canonical_grid(polygon)
    assert mask.ndim == 2
    assert max(mask.shape) <= MAX_DIM
    assert mask.shape[1] > mask.shape[0]
    assert mask.sum() >= 16
