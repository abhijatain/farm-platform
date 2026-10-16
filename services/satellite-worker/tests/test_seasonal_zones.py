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


def test_calculates_per_pixel_temporal_mean_without_saving_scene_data(monkeypatch):
    """Three cloud-clear scenes average onto a fixed 10m grid in memory."""
    import numpy as np
    from affine import Affine
    from types import SimpleNamespace
    from satellite_worker.ingestion import seasonal_zones as worker

    scenes = [_item(1, 0), _item(11, 10), _item(21, 4)]
    inside = np.ones((8, 8), dtype=bool)
    affine = Affine(10, 0, 100, 0, -10, 200)
    crs = "EPSG:32643"
    monkeypatch.setattr(worker, "canonical_grid", lambda _: (crs, affine, inside))
    monkeypatch.setattr(worker, "search_sentinel2", lambda **_kwargs: scenes)
    monkeypatch.setattr(worker, "build_analysis_grid", lambda **_kwargs: SimpleNamespace(
        pixel_count=64, transform=affine, crs=crs,
    ))
    monkeypatch.setattr(worker, "read_scl", lambda **_kwargs: SimpleNamespace(
        data=np.zeros((8, 8)), invalid_mask=np.zeros((8, 8), dtype=bool),
    ))
    def band(*, item, grid, band_name):
        ndvi = [0.4, 0.6, 0.8][scenes.index(item)]
        refl = 0.1 if band_name == "red" else 0.1 * (1 + ndvi) / (1 - ndvi)
        return SimpleNamespace(asset=None, data=np.full((8, 8), refl, dtype="float32"),
                               invalid_mask=np.zeros((8, 8), dtype=bool))
    monkeypatch.setattr(worker, "read_spectral_band", band)
    monkeypatch.setattr(worker, "build_scene_valid_mask",
                        lambda **_kwargs: np.ones((8, 8), dtype=bool))
    monkeypatch.setattr(worker, "to_reflectance",
                        lambda *, item, asset, data: (data, None))
    result = worker.compute_season(
        {"type": "Polygon", "coordinates": []},
        date(2025,7,1), date(2025,7,31),
    )
    assert result["scene_count"] == 3
    assert result["width"] == 8 and result["height"] == 8
    assert result["mean_ndvi"] == 0.6
    assert all(abs(v - 0.6) < 0.001 for v in result["pixels"])
    assert result["weak_area_acres"] == 0
    assert result["strong_area_acres"] == 0
    assert "raster_uri" not in result and "scene_rasters" not in result
