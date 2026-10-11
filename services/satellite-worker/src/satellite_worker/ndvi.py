from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pystac
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform

from satellite_worker.stac import (
    NIR_ASSET_NAMES,
    RED_ASSET_NAMES,
    SCL_ASSET_NAMES,
    get_asset,
)

NODATA_VALUE = -9999.0


# If a large percentage of valid field pixels
# become exactly 1.0, something is almost
# certainly wrong with the radiometric pipeline.
MAX_EXACT_ONE_PERCENT = 10.0


# Sentinel-2 Scene Classification values
# we do NOT want for NDVI analysis.
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
class NDVIResult:
    raster_path: Path

    mean: float
    median: float

    minimum: float
    maximum: float

    std: float

    resolution_m: float

    pixel_count: int
    valid_pixel_count: int

    valid_pixel_percent: float


def calculate_ndvi(
    *,
    item: pystac.Item,
    field_geometry: dict,
    output_path: Path,
) -> NDVIResult:

    red_asset = get_asset(
        item,
        RED_ASSET_NAMES,
    )

    nir_asset = get_asset(
        item,
        NIR_ASSET_NAMES,
    )

    scl_asset = get_asset(
        item,
        SCL_ASSET_NAMES,
    )

    field_wgs84 = shape(field_geometry)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rasterio_environment = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
        "GDAL_HTTP_MULTIRANGE": "YES",
        "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
        "VSI_CACHE": "TRUE",
    }

    with rasterio.Env(**rasterio_environment):

        # ====================================================
        # RED BAND
        # ====================================================

        with rasterio.open(red_asset.href) as red_src:

            if red_src.crs is None:
                raise RuntimeError("Red band has no CRS.")

            transformer = Transformer.from_crs(
                "EPSG:4326",
                red_src.crs,
                always_xy=True,
            )

            field_projected = shapely_transform(
                transformer.transform,
                field_wgs84,
            )

            raw_window = from_bounds(
                *field_projected.bounds,
                transform=red_src.transform,
            )

            raw_window = raw_window.round_offsets().round_lengths()

            dataset_window = Window(
                0,
                0,
                red_src.width,
                red_src.height,
            )

            try:
                window = raw_window.intersection(dataset_window)

            except Exception as error:
                raise RuntimeError(
                    "Field does not overlap " "the selected Sentinel scene."
                ) from error

            width = int(window.width)

            height = int(window.height)

            if width <= 0 or height <= 0:
                raise RuntimeError("Calculated raster window " "is empty.")

            target_transform = red_src.window_transform(window)

            red = red_src.read(
                1,
                window=window,
                masked=True,
            )

            red_data = red.astype(np.float32).filled(np.nan)

            red_invalid = np.ma.getmaskarray(red)

            # ====================================================
            # NIR BAND
            #
            # B08 and B04 are both nominally 10 m.
            #
            # WarpedVRT keeps the grids aligned even if
            # there is a small source-grid difference.
            # ====================================================

            with rasterio.open(nir_asset.href) as nir_src:

                with WarpedVRT(
                    nir_src,
                    crs=red_src.crs,
                    transform=target_transform,
                    width=width,
                    height=height,
                    resampling=Resampling.bilinear,
                ) as nir_vrt:

                    nir = nir_vrt.read(
                        1,
                        masked=True,
                    )

            nir_data = nir.astype(np.float32).filled(np.nan)

            nir_invalid = np.ma.getmaskarray(nir)

            # ====================================================
            # SCL
            #
            # SCL is 20 m, therefore it is resampled to
            # the 10 m B04 grid.
            #
            # Nearest-neighbour MUST be used because these
            # are categorical class values.
            # ====================================================

            with rasterio.open(scl_asset.href) as scl_src:

                with WarpedVRT(
                    scl_src,
                    crs=red_src.crs,
                    transform=target_transform,
                    width=width,
                    height=height,
                    resampling=Resampling.nearest,
                ) as scl_vrt:

                    scl = scl_vrt.read(1)

            # ====================================================
            # EXACT FIELD MASK
            # ====================================================

            inside_field = geometry_mask(
                [mapping(field_projected)],
                out_shape=(
                    height,
                    width,
                ),
                transform=target_transform,
                invert=True,
                all_touched=False,
            )

            pixel_count = int(inside_field.sum())

            if pixel_count == 0:
                raise RuntimeError(
                    "Field is too small or does "
                    "not contain any Sentinel "
                    "pixel centres."
                )

            # ====================================================
            # CLOUD / INVALID PIXEL MASK
            # ====================================================

            scl_valid = ~np.isin(
                scl,
                list(INVALID_SCL_VALUES),
            )

            # ====================================================
            # NDVI
            #
            # IMPORTANT
            # ---------
            #
            # For the current Earth Search sentinel-2-l2a
            # COGs we calculate NDVI directly from the B04
            # and B08 COG pixel values:
            #
            # NDVI = (NIR - RED) / (NIR + RED)
            #
            # A common multiplicative scale cancels:
            #
            # (s*NIR - s*RED)
            # ----------------
            # (s*NIR + s*RED)
            #
            # =
            #
            # (NIR - RED)
            # -----------
            # (NIR + RED)
            #
            # We intentionally do NOT blindly apply the
            # raster:bands additive offset here.
            #
            # The previous implementation did:
            #
            # DN * scale + offset
            #
            # and produced a large number of pixels that
            # exceeded 1.0 and were subsequently clipped
            # to exactly 1.0.
            #
            # Clipping hid the calibration problem.
            #
            # This implementation NEVER clips NDVI.
            # Nonphysical values are rejected instead.
            # ====================================================

            denominator = nir_data + red_data

            base_valid = (
                inside_field
                & ~red_invalid
                & ~nir_invalid
                & scl_valid
                & np.isfinite(red_data)
                & np.isfinite(nir_data)
                & (red_data > 0)
                & (nir_data > 0)
                & (np.abs(denominator) > 1e-6)
            )

            candidate_ndvi = np.full(
                (
                    height,
                    width,
                ),
                np.nan,
                dtype=np.float32,
            )

            candidate_ndvi[base_valid] = (
                nir_data[base_valid] - red_data[base_valid]
            ) / denominator[base_valid]

            # ====================================================
            # PHYSICAL NDVI VALIDATION
            #
            # We reject values outside the mathematically
            # valid NDVI range instead of clipping them.
            # ====================================================

            physical_ndvi = (
                np.isfinite(candidate_ndvi)
                & (candidate_ndvi >= -1.0)
                & (candidate_ndvi <= 1.0)
            )

            rejected_nonphysical = int((base_valid & ~physical_ndvi).sum())

            if rejected_nonphysical > 0:
                print(
                    "Warning: rejected "
                    f"{rejected_nonphysical} "
                    "nonphysical NDVI pixels "
                    "outside [-1, 1]."
                )

            valid = base_valid & physical_ndvi

            valid_pixel_count = int(valid.sum())

            if valid_pixel_count == 0:
                raise RuntimeError(
                    "No valid cloud-free NDVI "
                    "pixels exist inside this "
                    "field for this scene."
                )

            valid_pixel_percent = valid_pixel_count / pixel_count * 100.0

            # ====================================================
            # FINAL NDVI VALUES
            # ====================================================

            ndvi_values = candidate_ndvi[valid]

            ndvi = np.full(
                (
                    height,
                    width,
                ),
                NODATA_VALUE,
                dtype=np.float32,
            )

            ndvi[valid] = ndvi_values

            # ====================================================
            # FIELD STATISTICS
            # ====================================================

            mean = float(np.mean(ndvi_values))

            median = float(np.median(ndvi_values))

            minimum = float(np.min(ndvi_values))

            maximum = float(np.max(ndvi_values))

            std = float(np.std(ndvi_values))

            resolution_m = float(abs(target_transform.a))

            # ====================================================
            # DISTRIBUTION DIAGNOSTICS
            #
            # These are intentionally printed while we're
            # validating the Sentinel pipeline.
            # ====================================================

            p05 = float(
                np.percentile(
                    ndvi_values,
                    5,
                )
            )

            p25 = float(
                np.percentile(
                    ndvi_values,
                    25,
                )
            )

            p75 = float(
                np.percentile(
                    ndvi_values,
                    75,
                )
            )

            p95 = float(
                np.percentile(
                    ndvi_values,
                    95,
                )
            )

            exactly_one_count = int(
                np.isclose(
                    ndvi_values,
                    1.0,
                    atol=1e-6,
                ).sum()
            )

            exactly_one_percent = exactly_one_count / valid_pixel_count * 100.0

            near_one_count = int((ndvi_values >= 0.95).sum())

            near_one_percent = near_one_count / valid_pixel_count * 100.0

            print()
            print("NDVI diagnostics")

            print("----------------")

            print(f"Scene: {item.id}")

            print(f"Field pixels: " f"{pixel_count}")

            print(f"Valid pixels: " f"{valid_pixel_count}")

            print("Valid coverage: " f"{valid_pixel_percent:.1f}%")

            print(f"Min: {minimum:.4f}")

            print(f"P05: {p05:.4f}")

            print(f"P25: {p25:.4f}")

            print(f"Median: {median:.4f}")

            print(f"Mean: {mean:.4f}")

            print(f"P75: {p75:.4f}")

            print(f"P95: {p95:.4f}")

            print(f"Max: {maximum:.4f}")

            print(
                "Exactly 1.0: " f"{exactly_one_count} " f"({exactly_one_percent:.1f}%)"
            )

            print(">= 0.95: " f"{near_one_count} " f"({near_one_percent:.1f}%)")

            print("Rejected nonphysical: " f"{rejected_nonphysical}")

            print()

            # ====================================================
            # SATURATION SAFETY CHECK
            #
            # NDVI exactly equal to 1 means the red signal
            # is effectively zero.
            #
            # A substantial portion of a normal crop field
            # being exactly 1.0 is highly suspicious.
            #
            # This prevents us from silently writing another
            # corrupted COG and then generating false anomaly
            # polygons from it.
            # ====================================================

            if exactly_one_percent > MAX_EXACT_ONE_PERCENT:
                raise RuntimeError(
                    "Suspicious NDVI distribution "
                    f"for scene {item.id}: "
                    f"{exactly_one_percent:.1f}% "
                    "of valid pixels are exactly "
                    "1.0. The raster was rejected "
                    "instead of being saved."
                )

            # ====================================================
            # WRITE TEMPORARY GEOTIFF
            # ====================================================

            temporary_file = tempfile.NamedTemporaryFile(
                suffix=".tif",
                delete=False,
            )

            temporary_path = Path(temporary_file.name)

            temporary_file.close()

            try:

                with rasterio.open(
                    temporary_path,
                    "w",
                    driver="GTiff",
                    height=height,
                    width=width,
                    count=1,
                    dtype="float32",
                    crs=red_src.crs,
                    transform=target_transform,
                    nodata=NODATA_VALUE,
                    compress="DEFLATE",
                ) as output:

                    output.write(
                        ndvi,
                        1,
                    )

                    output.update_tags(
                        index="NDVI",
                        scene_id=item.id,
                        calculation=("direct_normalized_" "difference"),
                        source=("earth-search-" "sentinel-2-l2a"),
                        valid_pixel_percent=(f"{valid_pixel_percent:.4f}"),
                    )

                # ================================================
                # CONVERT TO CLOUD OPTIMIZED GEOTIFF
                # ================================================

                cog_profile = cog_profiles.get("deflate")

                cog_translate(
                    temporary_path,
                    output_path,
                    cog_profile,
                    in_memory=False,
                    quiet=True,
                )

            finally:

                if temporary_path.exists():
                    os.unlink(temporary_path)

    return NDVIResult(
        raster_path=output_path,
        mean=mean,
        median=median,
        minimum=minimum,
        maximum=maximum,
        std=std,
        resolution_m=resolution_m,
        pixel_count=pixel_count,
        valid_pixel_count=valid_pixel_count,
        valid_pixel_percent=valid_pixel_percent,
    )
