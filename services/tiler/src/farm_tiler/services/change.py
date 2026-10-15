"""Build server-side pixel-change previews from comparable Cloud Optimized GeoTIFFs."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.vrt import WarpedVRT

from farm_tiler.storage.gcs_path import (
    signed_gcs_get_url,
)


RASTERIO_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN":
        "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS":
        ".tif,.TIF,.tiff,.TIFF",
    "GDAL_HTTP_MULTIRANGE":
        "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES":
        "YES",
    "VSI_CACHE":
        "TRUE",
}

SQUARE_METRES_PER_ACRE = (
    4046.8564224
)


@dataclass(frozen=True)
class ChangeRaster:
    change: np.ndarray
    valid: np.ndarray

    pixel_area_sqm: float

    width: int
    height: int


def _pixel_area_sqm(
    dataset: rasterio.io.DatasetReader,
) -> float:
    if (
        dataset.crs is None
        or not dataset.crs.is_projected
    ):
        raise ValueError(
            "Change area requires a projected raster CRS."
        )

    transform = dataset.transform

    area = abs(
        transform.a
        * transform.e
        - transform.b
        * transform.d
    )

    if (
        not np.isfinite(
            area
        )
        or area <= 0
    ):
        raise ValueError(
            "Raster has an invalid pixel area."
        )

    return float(
        area
    )


def read_change_raster(
    *,
    before_uri: str,
    after_uri: str,
) -> ChangeRaster:
    before_url = (
        signed_gcs_get_url(
            before_uri
        )
    )

    after_url = (
        signed_gcs_get_url(
            after_uri
        )
    )

    with rasterio.Env(
        **RASTERIO_ENV
    ):
        with rasterio.open(
            after_url
        ) as after_source:
            if (
                after_source.crs
                is None
            ):
                raise ValueError(
                    "After raster has no CRS."
                )

            after_values = (
                after_source.read(
                    1,
                    masked=True,
                )
                .astype(
                    np.float32
                )
            )

            with rasterio.open(
                before_url
            ) as before_source:
                if (
                    before_source.crs
                    is None
                ):
                    raise ValueError(
                        "Before raster has no CRS."
                    )

                with WarpedVRT(
                    before_source,
                    crs=after_source.crs,
                    transform=(
                        after_source
                        .transform
                    ),
                    width=(
                        after_source.width
                    ),
                    height=(
                        after_source.height
                    ),
                    resampling=(
                        Resampling.bilinear
                    ),
                ) as before_vrt:
                    before_values = (
                        before_vrt.read(
                            1,
                            masked=True,
                        )
                        .astype(
                            np.float32
                        )
                    )

            before_data = (
                before_values.filled(
                    np.nan
                )
            )

            after_data = (
                after_values.filled(
                    np.nan
                )
            )

            valid = (
                ~np.ma.getmaskarray(
                    before_values
                )
                & ~np.ma.getmaskarray(
                    after_values
                )
                & np.isfinite(
                    before_data
                )
                & np.isfinite(
                    after_data
                )
            )

            if not np.any(
                valid
            ):
                raise ValueError(
                    "The selected rasters have no overlapping valid pixels."
                )

            change = np.full(
                (
                    after_source.height,
                    after_source.width,
                ),
                np.nan,
                dtype=np.float32,
            )

            change[
                valid
            ] = (
                after_data[
                    valid
                ]
                - before_data[
                    valid
                ]
            )

            return ChangeRaster(
                change=change,
                valid=valid,
                pixel_area_sqm=(
                    _pixel_area_sqm(
                        after_source
                    )
                ),
                width=(
                    after_source.width
                ),
                height=(
                    after_source.height
                ),
            )


def summarize_change(
    *,
    raster: ChangeRaster,
    threshold: float,
) -> dict:
    if threshold < 0:
        raise ValueError(
            "Change threshold cannot be negative."
        )

    values = raster.change[
        raster.valid
    ]

    increased = (
        raster.valid
        & (
            raster.change
            > threshold
        )
    )

    decreased = (
        raster.valid
        & (
            raster.change
            < -threshold
        )
    )

    stable = (
        raster.valid
        & ~increased
        & ~decreased
    )

    valid_count = int(
        raster.valid.sum()
    )

    increased_count = int(
        increased.sum()
    )

    decreased_count = int(
        decreased.sum()
    )

    stable_count = int(
        stable.sum()
    )

    def area(
        count: int,
    ) -> float:
        return float(
            count
            * raster.pixel_area_sqm
        )

    def acres(
        area_sqm: float,
    ) -> float:
        return float(
            area_sqm
            / SQUARE_METRES_PER_ACRE
        )

    def percent(
        count: int,
    ) -> float:
        if valid_count <= 0:
            return 0.0

        return float(
            count
            / valid_count
            * 100.0
        )

    valid_area = area(
        valid_count
    )

    increased_area = area(
        increased_count
    )

    decreased_area = area(
        decreased_count
    )

    stable_area = area(
        stable_count
    )

    return {
        "threshold":
            float(
                threshold
            ),

        "valid_pixel_count":
            valid_count,

        "mean_change":
            float(
                np.mean(
                    values
                )
            ),

        "median_change":
            float(
                np.median(
                    values
                )
            ),

        "minimum_change":
            float(
                np.min(
                    values
                )
            ),

        "maximum_change":
            float(
                np.max(
                    values
                )
            ),

        "valid_area_sqm":
            valid_area,

        "valid_area_acres":
            acres(
                valid_area
            ),

        "increased_pixel_count":
            increased_count,

        "increased_percent":
            percent(
                increased_count
            ),

        "increased_area_sqm":
            increased_area,

        "increased_area_acres":
            acres(
                increased_area
            ),

        "decreased_pixel_count":
            decreased_count,

        "decreased_percent":
            percent(
                decreased_count
            ),

        "decreased_area_sqm":
            decreased_area,

        "decreased_area_acres":
            acres(
                decreased_area
            ),

        "stable_pixel_count":
            stable_count,

        "stable_percent":
            percent(
                stable_count
            ),

        "stable_area_sqm":
            stable_area,

        "stable_area_acres":
            acres(
                stable_area
            ),
    }


def _interpolate(
    start: np.ndarray,
    end: np.ndarray,
    factor: np.ndarray,
) -> np.ndarray:
    return (
        start[
            None,
            None,
            :
        ]
        + (
            end
            - start
        )[
            None,
            None,
            :
        ]
        * factor[
            :,
            :,
            None,
        ]
    )


def render_change_png(
    *,
    raster: ChangeRaster,
    max_abs: float,
) -> bytes:
    if max_abs <= 0:
        raise ValueError(
            "max_abs must be greater than zero."
        )

    normalized = np.clip(
        raster.change
        / float(
            max_abs
        ),
        -1.0,
        1.0,
    )

    negative = (
        normalized
        < 0
    )

    positive = (
        normalized
        > 0
    )

    center = np.array(
        [
            247,
            247,
            247,
        ],
        dtype=np.float32,
    )

    negative_color = np.array(
        [
            196,
            46,
            43,
        ],
        dtype=np.float32,
    )

    positive_color = np.array(
        [
            34,
            139,
            72,
        ],
        dtype=np.float32,
    )

    rgb = np.broadcast_to(
        center,
        (
            raster.height,
            raster.width,
            3,
        ),
    ).copy()

    negative_factor = np.clip(
        -normalized,
        0.0,
        1.0,
    )

    positive_factor = np.clip(
        normalized,
        0.0,
        1.0,
    )

    negative_rgb = _interpolate(
        center,
        negative_color,
        negative_factor,
    )

    positive_rgb = _interpolate(
        center,
        positive_color,
        positive_factor,
    )

    rgb[
        negative
    ] = negative_rgb[
        negative
    ]

    rgb[
        positive
    ] = positive_rgb[
        positive
    ]

    alpha = np.where(
        raster.valid,
        255,
        0,
    ).astype(
        np.uint8
    )

    rgba = np.concatenate(
        [
            np.clip(
                rgb,
                0,
                255,
            ).astype(
                np.uint8
            ),
            alpha[
                :,
                :,
                None,
            ],
        ],
        axis=2,
    )

    bands = np.moveaxis(
        rgba,
        2,
        0,
    )

    with MemoryFile() as memory:
        with memory.open(
            driver="PNG",
            width=raster.width,
            height=raster.height,
            count=4,
            dtype="uint8",
        ) as destination:
            destination.write(
                bands
            )

        return memory.read()
