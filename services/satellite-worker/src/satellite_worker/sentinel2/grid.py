from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pystac
import rasterio

from affine import Affine
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from satellite_worker.sentinel2.bands import (
    SentinelBandDefinition,
    get_band_asset,
)


RASTERIO_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": ("EMPTY_DIR"),
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": (".tif,.TIF"),
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": ("YES"),
    "VSI_CACHE": "TRUE",
}


# Sentinel-2 Scene Classification
# values excluded from field analysis.
#
# 0  No data
# 1  Saturated / defective
# 2  Dark area / cast shadow
# 3  Cloud shadow
# 7  Unclassified
# 8  Medium cloud probability
# 9  High cloud probability
# 10 Thin cirrus
# 11 Snow / ice
INVALID_SCL_VALUES = {
    0,
    1,
    2,
    3,
    7,
    8,
    9,
    10,
    11,
}


@dataclass
class AnalysisGrid:
    crs: CRS

    transform: Affine

    width: int
    height: int

    field_projected: BaseGeometry

    inside_field: np.ndarray

    reference_href: str
    reference_window: Window

    resolution_m: float

    @property
    def pixel_count(
        self,
    ) -> int:
        return int(self.inside_field.sum())


@dataclass
class SpectralBand:
    name: str

    asset_key: str

    asset: pystac.Asset

    definition: SentinelBandDefinition

    data: np.ndarray

    invalid_mask: np.ndarray


@dataclass
class ClassificationBand:
    name: str

    asset_key: str

    asset: pystac.Asset

    definition: SentinelBandDefinition

    data: np.ndarray

    invalid_mask: np.ndarray


def build_analysis_grid(
    *,
    item: pystac.Item,
    field_geometry: dict,
    reference_band: str = "red",
) -> AnalysisGrid:
    (
        _,
        reference_asset,
        _,
    ) = get_band_asset(
        item,
        reference_band,
    )

    field_wgs84 = shape(field_geometry)

    with rasterio.Env(**RASTERIO_ENV):
        with rasterio.open(reference_asset.href) as reference_src:
            if reference_src.crs is None:
                raise RuntimeError("Reference Sentinel-2 " "band has no CRS.")

            transformer = Transformer.from_crs(
                "EPSG:4326",
                reference_src.crs,
                always_xy=True,
            )

            field_projected = shapely_transform(
                transformer.transform,
                field_wgs84,
            )

            raw_window = from_bounds(
                *field_projected.bounds,
                transform=(reference_src.transform),
            )

            raw_window = raw_window.round_offsets().round_lengths()

            dataset_window = Window(
                0,
                0,
                reference_src.width,
                reference_src.height,
            )

            try:
                window = raw_window.intersection(dataset_window)

            except Exception as error:
                raise RuntimeError(
                    "Field does not overlap " "the Sentinel-2 scene."
                ) from error

            width = int(window.width)

            height = int(window.height)

            if width <= 0 or height <= 0:
                raise RuntimeError("Calculated Sentinel-2 " "analysis window is empty.")

            target_transform = reference_src.window_transform(window)

            inside_field = geometry_mask(
                [mapping(field_projected)],
                out_shape=(
                    height,
                    width,
                ),
                transform=(target_transform),
                invert=True,
                all_touched=False,
            )

            pixel_count = int(inside_field.sum())

            if pixel_count == 0:
                raise RuntimeError(
                    "Field is too small or "
                    "does not contain any "
                    "Sentinel pixel centres."
                )

            resolution_m = float(abs(target_transform.a))

            return AnalysisGrid(
                crs=reference_src.crs,
                transform=(target_transform),
                width=width,
                height=height,
                field_projected=(field_projected),
                inside_field=(inside_field),
                reference_href=(reference_asset.href),
                reference_window=window,
                resolution_m=(resolution_m),
            )


def read_spectral_band(
    *,
    item: pystac.Item,
    grid: AnalysisGrid,
    band_name: str,
) -> SpectralBand:
    (
        asset_key,
        asset,
        definition,
    ) = get_band_asset(
        item,
        band_name,
    )

    with rasterio.Env(**RASTERIO_ENV):
        with rasterio.open(asset.href) as source:
            if source.crs is None:
                raise RuntimeError(f"Band {band_name!r} " "has no CRS.")

            # The reference B04 band is
            # read directly. This keeps
            # behaviour identical to the
            # working NDVI implementation.
            if asset.href == grid.reference_href:
                values = source.read(
                    1,
                    window=(grid.reference_window),
                    masked=True,
                )

            else:
                with WarpedVRT(
                    source,
                    crs=grid.crs,
                    transform=(grid.transform),
                    width=grid.width,
                    height=grid.height,
                    resampling=(definition.resampling),
                ) as vrt:
                    values = vrt.read(
                        1,
                        masked=True,
                    )

    data = values.astype(np.float32).filled(np.nan)

    invalid_mask = np.ma.getmaskarray(values)

    return SpectralBand(
        name=band_name,
        asset_key=asset_key,
        asset=asset,
        definition=definition,
        data=data,
        invalid_mask=(invalid_mask),
    )


def read_scl(
    *,
    item: pystac.Item,
    grid: AnalysisGrid,
) -> ClassificationBand:
    (
        asset_key,
        asset,
        definition,
    ) = get_band_asset(
        item,
        "scl",
    )

    with rasterio.Env(**RASTERIO_ENV):
        with rasterio.open(asset.href) as source:
            if source.crs is None:
                raise RuntimeError("SCL asset has no CRS.")

            with WarpedVRT(
                source,
                crs=grid.crs,
                transform=grid.transform,
                width=grid.width,
                height=grid.height,
                resampling=(definition.resampling),
            ) as vrt:
                values = vrt.read(
                    1,
                    masked=True,
                )

    invalid_mask = np.ma.getmaskarray(values)

    data = values.filled(0).astype(np.int16)

    return ClassificationBand(
        name="scl",
        asset_key=asset_key,
        asset=asset,
        definition=definition,
        data=data,
        invalid_mask=(invalid_mask),
    )


def build_scene_valid_mask(
    *,
    grid: AnalysisGrid,
    scl: ClassificationBand,
    bands: list[SpectralBand],
) -> np.ndarray:
    valid = grid.inside_field.copy()

    valid &= ~scl.invalid_mask

    valid &= ~np.isin(
        scl.data,
        list(INVALID_SCL_VALUES),
    )

    for band in bands:
        valid &= ~band.invalid_mask

        valid &= np.isfinite(band.data)

    return valid
