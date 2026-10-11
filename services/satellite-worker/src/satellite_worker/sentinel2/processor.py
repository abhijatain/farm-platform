from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pystac
import rasterio
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

from satellite_worker.sentinel2.grid import (
    AnalysisGrid,
    build_analysis_grid,
    build_scene_valid_mask,
    read_scl,
    read_spectral_band,
)
from satellite_worker.sentinel2.indices import METRIC_DEFINITIONS, calculate_metric
from satellite_worker.sentinel2.reflectance import (
    ReflectanceCalibration,
    to_reflectance,
)

NODATA_VALUE = -9999.0


@dataclass
class MetricResult:
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

    calibration_methods: dict[
        str,
        str,
    ]


def write_metric_cog(
    *,
    values: np.ndarray,
    valid_mask: np.ndarray,
    grid: AnalysisGrid,
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

    raster[valid_mask] = values[valid_mask]

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
            height=grid.height,
            width=grid.width,
            count=1,
            dtype="float32",
            crs=grid.crs,
            transform=grid.transform,
            nodata=NODATA_VALUE,
            tiled=True,
            compress="deflate",
        ) as destination:
            destination.write(
                raster,
                1,
            )

            destination.update_tags(
                index=(metric_type.upper()),
                metric_type=(metric_type),
                scene_id=scene_id,
                output_resolution_m=(grid.resolution_m),
            )

        profile = cog_profiles.get("deflate")

        cog_translate(
            str(temporary_path),
            str(output_path),
            profile,
            in_memory=False,
            quiet=True,
        )

    finally:
        try:
            os.unlink(temporary_path)

        except FileNotFoundError:
            pass


def process_metrics(
    *,
    item: pystac.Item,
    field_geometry: dict,
    output_directory: Path,
    metric_types: tuple[
        str,
        ...,
    ] = (
        "ndvi",
        "ndre",
        "ndmi",
        "gndvi",
        "evi2",
        "ndwi",
        "savi",
        "msavi",
        "bsi",
        "ndti",
        "ccci",
        "reci",
        "mcari",
    ),
) -> list[MetricResult]:
    for metric_type in metric_types:
        if metric_type not in METRIC_DEFINITIONS:
            raise ValueError(f"Unsupported metric " f"{metric_type!r}")

    grid = build_analysis_grid(
        item=item,
        field_geometry=(field_geometry),
    )

    scl = read_scl(
        item=item,
        grid=grid,
    )

    required_band_names = {
        band_name
        for metric_type in metric_types
        for band_name in METRIC_DEFINITIONS[metric_type].bands
    }

    spectral_bands = {}

    reflectance = {}

    calibrations: dict[
        str,
        ReflectanceCalibration,
    ] = {}

    for band_name in sorted(required_band_names):
        band = read_spectral_band(
            item=item,
            grid=grid,
            band_name=band_name,
        )

        spectral_bands[band_name] = band

        (
            reflectance_values,
            calibration,
        ) = to_reflectance(
            item=item,
            asset=band.asset,
            data=band.data,
        )

        reflectance[band_name] = reflectance_values

        calibrations[band_name] = calibration

    results: list[MetricResult] = []

    for metric_type in metric_types:
        definition = METRIC_DEFINITIONS[metric_type]

        metric_bands = [spectral_bands[band_name] for band_name in definition.bands]

        scene_valid = build_scene_valid_mask(
            grid=grid,
            scl=scl,
            bands=metric_bands,
        )

        (
            metric_values,
            formula_valid,
        ) = calculate_metric(
            metric_type=(metric_type),
            reflectance={
                band_name: reflectance[band_name] for band_name in definition.bands
            },
        )

        valid = scene_valid & formula_valid & np.isfinite(metric_values)

        valid_pixel_count = int(valid.sum())

        if valid_pixel_count == 0:
            print(f"{metric_type.upper()}: " "no valid pixels; skipping.")

            continue

        values = metric_values[valid]

        mean = float(np.mean(values))

        median = float(np.median(values))

        minimum = float(np.min(values))

        maximum = float(np.max(values))

        std = float(np.std(values))

        valid_pixel_percent = valid_pixel_count / grid.pixel_count * 100.0

        output_path = output_directory / (f"{item.id}_" f"{metric_type}.tif")

        write_metric_cog(
            values=metric_values,
            valid_mask=valid,
            grid=grid,
            output_path=output_path,
            metric_type=metric_type,
            scene_id=item.id,
        )

        calibration_methods = {
            band_name: calibrations[band_name].method for band_name in definition.bands
        }

        result = MetricResult(
            metric_type=metric_type,
            raster_path=output_path,
            mean=mean,
            median=median,
            minimum=minimum,
            maximum=maximum,
            std=std,
            native_resolution_m=(definition.native_resolution_m),
            output_resolution_m=(grid.resolution_m),
            pixel_count=(grid.pixel_count),
            valid_pixel_count=(valid_pixel_count),
            valid_pixel_percent=(valid_pixel_percent),
            formula_version=(definition.formula_version),
            calibration_methods=(calibration_methods),
        )

        results.append(result)

        print()
        print(metric_type.upper())

        print(
            "  valid:",
            f"{valid_pixel_percent:.1f}%",
        )

        print(
            "  mean:",
            f"{mean:.4f}",
        )

        print(
            "  median:",
            f"{median:.4f}",
        )

        print(
            "  range:",
            f"{minimum:.4f}",
            "->",
            f"{maximum:.4f}",
        )

        print(
            "  native:",
            definition.native_resolution_m,
            "m",
        )

        print(
            "  output:",
            grid.resolution_m,
            "m",
        )

    return results
