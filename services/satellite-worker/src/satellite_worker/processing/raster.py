"""Share aligned metric raster processing across radar and thermal sensors."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
import time
from urllib.request import urlopen

import numpy as np
import pystac
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform


NODATA_VALUE = -9999.0

RASTERIO_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    # Sentinel-1 RTC assets on Planetary Computer use .tiff while
    # Sentinel-2/Landsat commonly use .tif. GDAL rejects remote files whose
    # extension is not explicitly allowed here.
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff,.TIFF",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "VSI_CACHE": "TRUE",
}


@dataclass
class RasterGrid:
    crs: rasterio.crs.CRS
    transform: Affine

    width: int
    height: int

    inside_field: np.ndarray

    reference_href: str
    reference_window: Window

    resolution_m: float

    @property
    def pixel_count(self) -> int:
        return int(
            self.inside_field.sum()
        )


@dataclass
class DerivedMetricResult:
    metric_type: str
    raster_path: Path

    mean: float
    median: float
    minimum: float
    maximum: float
    std: float

    native_resolution_m: float
    output_resolution_m: float

    pixel_count: int
    valid_pixel_count: int
    valid_pixel_percent: float

    formula_version: str
    calibration_methods: dict[str, str]

    source_name: str
    metadata_json: dict = field(
        default_factory=dict,
    )


_PC_TOKEN_CACHE: dict[
    str,
    tuple[
        float,
        str,
    ],
] = {}


def _planetary_computer_token(
    collection_id: str,
) -> str:
    now = time.monotonic()

    cached = _PC_TOKEN_CACHE.get(
        collection_id
    )

    if (
        cached is not None
        and cached[0] > now
    ):
        return cached[1]

    url = (
        "https://planetarycomputer.microsoft.com/"
        "api/sas/v1/token/"
        f"{collection_id}"
    )

    with urlopen(
        url,
        timeout=30,
    ) as response:
        payload = json.load(
            response
        )

    token = str(
        payload[
            "token"
        ]
    ).lstrip("?")

    # Planetary Computer SAS lifetimes can change. Cache conservatively for
    # 30 minutes so a continuously-running worker refreshes well before expiry.
    _PC_TOKEN_CACHE[
        collection_id
    ] = (
        now + 30 * 60,
        token,
    )

    return token


def sign_planetary_computer_item(
    item: pystac.Item,
) -> pystac.Item:
    collection_id = (
        item.collection_id
        or ""
    )

    token = (
        _planetary_computer_token(
            collection_id
        )
    )

    signed = item.clone()

    for asset in signed.assets.values():
        href = asset.href

        if (
            ".blob.core.windows.net/"
            not in href
        ):
            continue

        separator = (
            "&"
            if "?" in href
            else "?"
        )

        asset.href = (
            href
            + separator
            + token
        )

    return signed


def build_grid_from_asset(
    *,
    item: pystac.Item,
    field_geometry: dict,
    asset_key: str,
) -> RasterGrid:
    asset = item.assets[
        asset_key
    ]

    field_wgs84 = shape(
        field_geometry
    )

    with rasterio.Env(
        **RASTERIO_ENV
    ):
        with rasterio.open(
            asset.href
        ) as source:
            if source.crs is None:
                raise RuntimeError(
                    f"Asset {asset_key!r} has no CRS."
                )

            transformer = Transformer.from_crs(
                "EPSG:4326",
                source.crs,
                always_xy=True,
            )

            field_projected = (
                shapely_transform(
                    transformer.transform,
                    field_wgs84,
                )
            )

            raw_window = from_bounds(
                *field_projected.bounds,
                transform=(
                    source.transform
                ),
            )

            raw_window = (
                raw_window
                .round_offsets()
                .round_lengths()
            )

            dataset_window = Window(
                0,
                0,
                source.width,
                source.height,
            )

            try:
                window = (
                    raw_window
                    .intersection(
                        dataset_window
                    )
                )

            except Exception as error:
                raise RuntimeError(
                    "Field does not overlap raster asset."
                ) from error

            width = int(
                window.width
            )
            height = int(
                window.height
            )

            if (
                width <= 0
                or height <= 0
            ):
                raise RuntimeError(
                    "Calculated raster window is empty."
                )

            target_transform = (
                source.window_transform(
                    window
                )
            )

            inside_field = (
                geometry_mask(
                    [
                        mapping(
                            field_projected
                        )
                    ],
                    out_shape=(
                        height,
                        width,
                    ),
                    transform=(
                        target_transform
                    ),
                    invert=True,
                    all_touched=False,
                )
            )

            if not np.any(
                inside_field
            ):
                raise RuntimeError(
                    "Field contains no raster pixel centres."
                )

            return RasterGrid(
                crs=source.crs,
                transform=(
                    target_transform
                ),
                width=width,
                height=height,
                inside_field=(
                    inside_field
                ),
                reference_href=(
                    asset.href
                ),
                reference_window=(
                    window
                ),
                resolution_m=float(
                    abs(
                        target_transform.a
                    )
                ),
            )


def read_asset_to_grid(
    *,
    item: pystac.Item,
    grid: RasterGrid,
    asset_key: str,
    resampling: Resampling,
) -> tuple[
    np.ndarray,
    np.ndarray,
    pystac.Asset,
]:
    asset = item.assets[
        asset_key
    ]

    with rasterio.Env(
        **RASTERIO_ENV
    ):
        with rasterio.open(
            asset.href
        ) as source:
            if source.crs is None:
                raise RuntimeError(
                    f"Asset {asset_key!r} has no CRS."
                )

            if (
                asset.href
                == grid.reference_href
            ):
                values = source.read(
                    1,
                    window=(
                        grid.reference_window
                    ),
                    masked=True,
                )

            else:
                with WarpedVRT(
                    source,
                    crs=grid.crs,
                    transform=(
                        grid.transform
                    ),
                    width=grid.width,
                    height=grid.height,
                    resampling=resampling,
                ) as vrt:
                    values = vrt.read(
                        1,
                        masked=True,
                    )

    data = (
        values
        .astype(
            np.float32
        )
        .filled(
            np.nan
        )
    )

    invalid = (
        np.ma.getmaskarray(
            values
        )
    )

    return (
        data,
        invalid,
        asset,
    )


def write_derived_metric_cog(
    *,
    values: np.ndarray,
    valid_mask: np.ndarray,
    grid: RasterGrid,
    output_path: Path,
    metric_type: str,
    scene_id: str,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    raster = np.full(
        (
            grid.height,
            grid.width,
        ),
        NODATA_VALUE,
        dtype=np.float32,
    )

    raster[
        valid_mask
    ] = values[
        valid_mask
    ]

    temporary = tempfile.NamedTemporaryFile(
        suffix=".tif",
        delete=False,
    )

    temporary_path = Path(
        temporary.name
    )

    temporary.close()

    try:
        with rasterio.open(
            temporary_path,
            "w",
            driver="GTiff",
            height=grid.height,
            width=grid.width,
            count=1,
            dtype="float32",
            crs=grid.crs,
            transform=(
                grid.transform
            ),
            nodata=NODATA_VALUE,
            tiled=True,
            compress="deflate",
        ) as destination:
            destination.write(
                raster,
                1,
            )

            destination.update_tags(
                metric_type=(
                    metric_type
                ),
                scene_id=(
                    scene_id
                ),
                output_resolution_m=(
                    grid.resolution_m
                ),
            )

        profile = (
            cog_profiles.get(
                "deflate"
            )
        )

        cog_translate(
            str(
                temporary_path
            ),
            str(
                output_path
            ),
            profile,
            in_memory=False,
            quiet=True,
        )

    finally:
        try:
            os.unlink(
                temporary_path
            )

        except FileNotFoundError:
            pass


def build_metric_result(
    *,
    metric_type: str,
    values: np.ndarray,
    valid_mask: np.ndarray,
    grid: RasterGrid,
    output_directory: Path,
    scene_id: str,
    native_resolution_m: float,
    formula_version: str,
    source_name: str,
    calibration_methods: dict[str, str],
    metadata_json: dict | None = None,
) -> DerivedMetricResult | None:
    valid = (
        valid_mask
        & grid.inside_field
        & np.isfinite(
            values
        )
    )

    valid_pixel_count = int(
        valid.sum()
    )

    if valid_pixel_count == 0:
        return None

    selected = values[
        valid
    ]

    output_path = (
        output_directory
        / (
            f"{scene_id}_"
            f"{metric_type}.tif"
        )
    )

    write_derived_metric_cog(
        values=values,
        valid_mask=valid,
        grid=grid,
        output_path=(
            output_path
        ),
        metric_type=(
            metric_type
        ),
        scene_id=(
            scene_id
        ),
    )

    return DerivedMetricResult(
        metric_type=metric_type,
        raster_path=(
            output_path
        ),
        mean=float(
            np.mean(
                selected
            )
        ),
        median=float(
            np.median(
                selected
            )
        ),
        minimum=float(
            np.min(
                selected
            )
        ),
        maximum=float(
            np.max(
                selected
            )
        ),
        std=float(
            np.std(
                selected
            )
        ),
        native_resolution_m=(
            native_resolution_m
        ),
        output_resolution_m=(
            grid.resolution_m
        ),
        pixel_count=(
            grid.pixel_count
        ),
        valid_pixel_count=(
            valid_pixel_count
        ),
        valid_pixel_percent=(
            valid_pixel_count
            / grid.pixel_count
            * 100.0
        ),
        formula_version=(
            formula_version
        ),
        calibration_methods=(
            calibration_methods
        ),
        source_name=(
            source_name
        ),
        metadata_json=(
            metadata_json
            or {}
        ),
    )
