import numpy as np

from satellite_worker.sentinel2.processor import (
    summarize_scene_coverage,
)


class _Grid:
    inside_field = np.array(
        [
            [True, True],
            [True, True],
        ],
        dtype=bool,
    )

    pixel_count = 4


class _SCL:
    invalid_mask = np.array(
        [
            [False, False],
            [False, False],
        ],
        dtype=bool,
    )

    # vegetation, high cloud, cloud shadow, thin cirrus
    data = np.array(
        [
            [4, 9],
            [3, 10],
        ],
        dtype=np.int16,
    )


def test_scene_coverage_reports_field_cloud_fraction() -> None:
    coverage = summarize_scene_coverage(
        grid=_Grid(),
        scl=_SCL(),
    )

    assert coverage.pixel_count == 4
    assert coverage.cloud_pixel_count == 3
    assert coverage.cloud_cover_percent == 75.0
    assert coverage.usable_pixel_count == 1
    assert coverage.usable_pixel_percent == 25.0
    assert coverage.excluded_pixel_percent == 75.0
