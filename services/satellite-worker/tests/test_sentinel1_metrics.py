import numpy as np
import pytest

from satellite_worker.process_sentinel1_field import (
    calculate_sar_metric_arrays,
)


def test_sentinel1_radar_metric_formulas() -> None:
    vv = np.array(
        [[0.2]],
        dtype=np.float32,
    )

    vh = np.array(
        [[0.05]],
        dtype=np.float32,
    )

    metrics = calculate_sar_metric_arrays(
        vv=vv,
        vh=vh,
    )

    assert metrics[
        "sar_vv_db"
    ][0, 0] == pytest.approx(
        10.0
        * np.log10(
            0.2
        ),
        abs=1e-6,
    )

    assert metrics[
        "sar_vh_db"
    ][0, 0] == pytest.approx(
        10.0
        * np.log10(
            0.05
        ),
        abs=1e-6,
    )

    assert metrics[
        "sar_vv_vh_ratio"
    ][0, 0] == pytest.approx(
        4.0,
        abs=1e-6,
    )

    assert metrics[
        "sar_rvi"
    ][0, 0] == pytest.approx(
        0.8,
        abs=1e-6,
    )
