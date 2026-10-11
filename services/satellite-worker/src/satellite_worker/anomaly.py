from __future__ import annotations

from dataclasses import (
    dataclass,
)
from pathlib import Path

import numpy as np
import rasterio

from pyproj import Transformer

from rasterio.features import (
    shapes,
)

from scipy.ndimage import (
    binary_dilation,
    label,
)

from shapely.geometry import (
    MultiPolygon,
    Polygon,
    mapping,
    shape,
)

from shapely.ops import (
    transform as shapely_transform,
    unary_union,
)


SQM_PER_ACRE = 4046.8564224


@dataclass
class AnomalyZone:
    zone_index: int

    severity: str

    pixel_count: int

    area_sqm: float
    area_acres: float

    zone_mean_value: float
    zone_min_value: float

    field_mean_value: float
    field_median_value: float

    threshold_value: float

    difference_from_field: float
    percent_difference: float | None

    geometry: dict

    metadata_json: dict


@dataclass
class AnomalyDetectionResult:
    zones: list[AnomalyZone]

    analysis: dict


def _polygon_parts(
    geometry,
) -> list[Polygon]:

    if geometry.is_empty:
        return []

    if isinstance(
        geometry,
        Polygon,
    ):
        return [geometry]

    if isinstance(
        geometry,
        MultiPolygon,
    ):
        return list(geometry.geoms)

    if hasattr(
        geometry,
        "geoms",
    ):

        parts: list[Polygon] = []

        for child in geometry.geoms:
            parts.extend(_polygon_parts(child))

        return parts

    return []


def _as_multipolygon(
    geometry,
) -> MultiPolygon | None:

    polygons = _polygon_parts(geometry)

    if not polygons:
        return None

    return MultiPolygon(polygons)


def _severity(
    *,
    absolute_deficit: float,
    percent_deficit: float | None,
) -> str:

    if absolute_deficit >= 0.20:
        return "high"

    if percent_deficit is not None and percent_deficit >= 35:
        return "high"

    if absolute_deficit >= 0.12:
        return "moderate"

    if percent_deficit is not None and percent_deficit >= 25:
        return "moderate"

    return "low"


def detect_ndvi_anomalies(
    *,
    raster_path: Path,
    field_geometry: dict,
    absolute_deficit_floor: float = 0.08,
    relative_deficit_fraction: float = 0.15,
    robust_sigma_factor: float = 1.5,
    min_cluster_pixels: int = 3,
    min_field_pixels: int = 12,
) -> AnomalyDetectionResult:

    with rasterio.open(raster_path) as src:

        if src.crs is None:
            raise RuntimeError("NDVI raster has no CRS.")

        if not src.crs.is_projected:
            raise RuntimeError(
                "NDVI raster must use a " "projected CRS for area " "calculation."
            )

        raster = src.read(
            1,
            masked=True,
        ).astype(np.float32)

        data = raster.filled(np.nan)

        masked = np.ma.getmaskarray(raster)

        valid = ~masked & np.isfinite(data) & (data >= -1.0) & (data <= 1.0)

        valid_values = data[valid]

        valid_pixel_count = int(valid.sum())

        if valid_pixel_count < min_field_pixels:

            return AnomalyDetectionResult(
                zones=[],
                analysis={
                    "status": "insufficient_pixels",
                    "method": "robust_mad_v1",
                    "valid_pixel_count": valid_pixel_count,
                    "minimum_required": min_field_pixels,
                    "zone_count": 0,
                },
            )

        field_mean = float(np.mean(valid_values))

        field_median = float(np.median(valid_values))

        mad = float(np.median(np.abs(valid_values - field_median)))

        robust_sigma = 1.4826 * mad

        absolute_requirement = absolute_deficit_floor

        relative_requirement = abs(field_median) * relative_deficit_fraction

        variability_requirement = robust_sigma * robust_sigma_factor

        required_deficit = max(
            absolute_requirement,
            relative_requirement,
            variability_requirement,
        )

        threshold = field_median - required_deficit

        candidate_mask = valid & (data <= threshold)

        candidate_pixel_count = int(candidate_mask.sum())

        structure = np.ones(
            (
                3,
                3,
            ),
            dtype=np.uint8,
        )

        component_labels, component_count = label(
            candidate_mask,
            structure=structure,
        )

        field_wgs84 = shape(field_geometry)

        to_raster = Transformer.from_crs(
            "EPSG:4326",
            src.crs,
            always_xy=True,
        )

        to_wgs84 = Transformer.from_crs(
            src.crs,
            "EPSG:4326",
            always_xy=True,
        )

        field_projected = shapely_transform(
            to_raster.transform,
            field_wgs84,
        )

        zones: list[AnomalyZone] = []

        zone_counter = 0

        for component_id in range(
            1,
            component_count + 1,
        ):

            component_mask = component_labels == component_id

            component_pixel_count = int(component_mask.sum())

            if component_pixel_count < min_cluster_pixels:
                continue

            component_values = data[component_mask]

            zone_mean = float(np.mean(component_values))

            zone_min = float(np.min(component_values))

            difference = zone_mean - field_median

            absolute_deficit = field_median - zone_mean

            if abs(field_median) > 0.05:

                percent_difference = difference / abs(field_median) * 100.0

                percent_deficit = -percent_difference

            else:

                percent_difference = None
                percent_deficit = None

            raster_polygons = []

            for geometry_json, value in shapes(
                component_mask.astype(np.uint8),
                mask=component_mask,
                transform=src.transform,
            ):

                if int(value) != 1:
                    continue

                raster_polygons.append(shape(geometry_json))

            if not raster_polygons:
                continue

            zone_projected = unary_union(raster_polygons)

            zone_projected = zone_projected.intersection(field_projected)

            if zone_projected.is_empty:
                continue

            zone_projected = zone_projected.buffer(0)

            area_sqm = float(zone_projected.area)

            if area_sqm <= 0:
                continue

            zone_wgs84 = shapely_transform(
                to_wgs84.transform,
                zone_projected,
            )

            zone_multi = _as_multipolygon(zone_wgs84)

            if zone_multi is None:
                continue

            expanded = binary_dilation(
                component_mask,
                structure=structure,
            )

            touches_nodata = bool(np.any(expanded & ~valid))

            severity = _severity(
                absolute_deficit=absolute_deficit,
                percent_deficit=percent_deficit,
            )

            zone_counter += 1

            zones.append(
                AnomalyZone(
                    zone_index=zone_counter,
                    severity=severity,
                    pixel_count=component_pixel_count,
                    area_sqm=area_sqm,
                    area_acres=(area_sqm / SQM_PER_ACRE),
                    zone_mean_value=zone_mean,
                    zone_min_value=zone_min,
                    field_mean_value=field_mean,
                    field_median_value=field_median,
                    threshold_value=threshold,
                    difference_from_field=difference,
                    percent_difference=percent_difference,
                    geometry=mapping(zone_multi),
                    metadata_json={
                        "touches_nodata": touches_nodata,
                        "absolute_deficit": absolute_deficit,
                        "percent_deficit": percent_deficit,
                    },
                )
            )

        analysis = {
            "status": "completed",
            "method": "robust_mad_v1",
            "field_mean": field_mean,
            "field_median": field_median,
            "mad": mad,
            "robust_sigma": robust_sigma,
            "absolute_deficit_floor": absolute_deficit_floor,
            "relative_deficit_fraction": relative_deficit_fraction,
            "robust_sigma_factor": robust_sigma_factor,
            "required_deficit": required_deficit,
            "threshold": threshold,
            "valid_pixel_count": valid_pixel_count,
            "candidate_pixel_count": candidate_pixel_count,
            "raw_component_count": int(component_count),
            "min_cluster_pixels": min_cluster_pixels,
            "zone_count": len(zones),
        }

        return AnomalyDetectionResult(
            zones=zones,
            analysis=analysis,
        )
