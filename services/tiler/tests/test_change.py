import numpy as np

from farm_tiler.change import (
    ChangeRaster,
    render_change_png,
    summarize_change,
)


def test_change_summary_splits_increase_decrease_and_stable() -> None:
    change = np.array(
        [
            [
                -0.20,
                -0.01,
            ],
            [
                0.05,
                0.30,
            ],
        ],
        dtype=np.float32,
    )

    valid = np.ones(
        (
            2,
            2,
        ),
        dtype=bool,
    )

    raster = ChangeRaster(
        change=change,
        valid=valid,
        pixel_area_sqm=100.0,
        width=2,
        height=2,
    )

    summary = summarize_change(
        raster=raster,
        threshold=0.03,
    )

    assert (
        summary[
            "valid_pixel_count"
        ]
        == 4
    )

    assert (
        summary[
            "increased_pixel_count"
        ]
        == 2
    )

    assert (
        summary[
            "decreased_pixel_count"
        ]
        == 1
    )

    assert (
        summary[
            "stable_pixel_count"
        ]
        == 1
    )

    assert (
        summary[
            "increased_area_sqm"
        ]
        == 200.0
    )

    assert (
        summary[
            "decreased_area_sqm"
        ]
        == 100.0
    )

    assert (
        summary[
            "stable_area_sqm"
        ]
        == 100.0
    )


def test_change_summary_ignores_invalid_pixels() -> None:
    change = np.array(
        [
            [
                0.5,
                0.5,
            ]
        ],
        dtype=np.float32,
    )

    valid = np.array(
        [
            [
                True,
                False,
            ],
        ],
        dtype=bool,
    )

    raster = ChangeRaster(
        change=change,
        valid=valid,
        pixel_area_sqm=100.0,
        width=2,
        height=1,
    )

    summary = summarize_change(
        raster=raster,
        threshold=0.03,
    )

    assert (
        summary[
            "valid_pixel_count"
        ]
        == 1
    )

    assert (
        summary[
            "increased_percent"
        ]
        == 100.0
    )


def test_change_preview_is_transparent_png() -> None:
    raster = ChangeRaster(
        change=np.array(
            [
                [
                    -0.2,
                    0.0,
                    0.2,
                ]
            ],
            dtype=np.float32,
        ),
        valid=np.array(
            [
                [
                    True,
                    False,
                    True,
                ],
            ],
            dtype=bool,
        ),
        pixel_area_sqm=100.0,
        width=3,
        height=1,
    )

    payload = render_change_png(
        raster=raster,
        max_abs=0.3,
    )

    assert payload.startswith(
        b"\x89PNG"
    )
