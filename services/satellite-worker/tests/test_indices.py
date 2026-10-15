"""Regression tests for indices, protecting established satellite behavior."""

import numpy as np
import pytest

from satellite_worker.sentinel2.indices import (
    METRIC_DEFINITIONS,
    calculate_metric,
)


REFLECTANCE = {
    "blue": np.array(
        [[0.10]],
        dtype=np.float32,
    ),
    "green": np.array(
        [[0.20]],
        dtype=np.float32,
    ),
    "red": np.array(
        [[0.30]],
        dtype=np.float32,
    ),
    "rededge1": np.array(
        [[0.40]],
        dtype=np.float32,
    ),
    "nir": np.array(
        [[0.70]],
        dtype=np.float32,
    ),
    "swir1": np.array(
        [[0.50]],
        dtype=np.float32,
    ),
    "swir2": np.array(
        [[0.45]],
        dtype=np.float32,
    ),
}


@pytest.mark.parametrize(
    "metric_type",
    sorted(
        METRIC_DEFINITIONS
    ),
)
def test_every_metric_produces_finite_value(
    metric_type: str,
) -> None:
    values, valid = calculate_metric(
        metric_type=metric_type,
        reflectance=REFLECTANCE,
    )

    assert valid[0, 0]
    assert np.isfinite(
        values[0, 0]
    )


def test_ndvi_formula() -> None:
    values, valid = calculate_metric(
        metric_type="ndvi",
        reflectance=REFLECTANCE,
    )

    assert valid[0, 0]
    assert values[0, 0] == pytest.approx(
        0.4,
        abs=1e-6,
    )


def test_ndmi_formula() -> None:
    values, valid = calculate_metric(
        metric_type="ndmi",
        reflectance=REFLECTANCE,
    )

    assert valid[0, 0]
    assert values[0, 0] == pytest.approx(
        (0.70 - 0.50)
        / (0.70 + 0.50),
        abs=1e-6,
    )
