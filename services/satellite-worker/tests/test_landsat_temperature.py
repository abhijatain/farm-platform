"""Regression tests for landsat temperature, protecting established satellite behavior."""

import numpy as np
import pytest

from satellite_worker.process_landsat_field import (
    landsat_qa_masks,
    landsat_temperature_celsius,
)


def test_landsat_collection2_temperature_scaling() -> None:
    raw = np.array(
        [[44_947]],
        dtype=np.float32,
    )

    celsius = landsat_temperature_celsius(
        raw_temperature=raw,
        scale=0.00341802,
        offset=149.0,
    )

    assert celsius[
        0,
        0,
    ] == pytest.approx(
        29.45,
        abs=0.05,
    )


def test_landsat_qa_cloud_and_shadow_are_invalid() -> None:
    clear = 0
    cloud = 1 << 3
    shadow = 1 << 4

    qa = np.array(
        [
            [
                clear,
                cloud,
                shadow,
            ]
        ],
        dtype=np.uint16,
    )

    invalid, cloudy = (
        landsat_qa_masks(
            qa
        )
    )

    assert not invalid[
        0,
        0,
    ]

    assert invalid[
        0,
        1,
    ]

    assert invalid[
        0,
        2,
    ]

    assert not cloudy[
        0,
        0,
    ]

    assert cloudy[
        0,
        1,
    ]

    assert cloudy[
        0,
        2,
    ]
