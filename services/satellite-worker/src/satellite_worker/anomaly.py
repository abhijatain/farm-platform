"""Find field-relative anomaly polygons from quality-screened raster metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import shapes
from scipy.ndimage import binary_dilation, label
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

from satellite_worker.anomaly_rules import METRIC_ANOMALY_RULES, MetricAnomalyRule

SQM_PER_ACRE = 4046.8564224


@dataclass
class AnomalyZone:
    zone_index: int

    anomaly_type: str

    severity: str

    pixel_count: int

    area_sqm: float
    area_acres: float

    zone_mean_value: float
    zone_min_value: float
    zone_max_value: float

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
            parts.extend(
                _polygon_parts(
                    child,
                )
            )

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
    robust_z: float | None,
    deviation_ratio: float,
) -> str:
    """
    Generic severity calculation.

    Prefer robust deviation from the field median.

    If MAD is zero or extremely small, fall back to comparing
    the zone's deviation against the minimum deviation required
    for that metric.
    """

    if robust_z is not None:
        if robust_z >= 3.0:
            return "high"

        if robust_z >= 2.0:
            return "moderate"

        return "low"

    if deviation_ratio >= 2.0:
        return "high"

    if deviation_ratio >= 1.5:
        return "moderate"

    return "low"


def _build_candidate_masks(
    *,
    rule: MetricAnomalyRule,
    data: np.ndarray,
    valid: np.ndarray,
    field_median: float,
    required_difference: float,
) -> list[
    tuple[
        str,
        float,
        np.ndarray,
    ]
]:
    """
    Return one or more directional anomaly masks.

    Low-direction metrics:
        NDVI, NDMI, NDRE, ...

    High-direction metrics:
        BSI

    Two-sided metrics:
        NDWI, NDTI

    Two-sided metrics deliberately produce separate low and
    high components so opposite anomaly directions cannot be
    merged into one zone.
    """

    low_threshold = field_median - required_difference

    high_threshold = field_median + required_difference

    if rule.direction == "low":
        return [
            (
                "below_field_baseline",
                low_threshold,
                valid & (data <= low_threshold),
            )
        ]

    if rule.direction == "high":
        return [
            (
                "above_field_baseline",
                high_threshold,
                valid & (data >= high_threshold),
            )
        ]

    if rule.direction == "two_sided":
        return [
            (
                "below_field_baseline",
                low_threshold,
                valid & (data <= low_threshold),
            ),
            (
                "above_field_baseline",
                high_threshold,
                valid & (data >= high_threshold),
            ),
        ]

    raise RuntimeError("Unsupported anomaly direction: " f"{rule.direction}")


def detect_metric_anomalies(
    *,
    metric_type: str,
    raster_path: Path,
    field_geometry: dict,
    minimum_difference: float | None = None,
    relative_difference_fraction: float = 0.15,
    robust_sigma_factor: float = 1.5,
    min_cluster_pixels: int = 3,
    min_field_pixels: int = 12,
) -> AnomalyDetectionResult:
    """
    Detect within-field spatial anomalies for one satellite metric.

    This detector compares pixels to the distribution of the
    same field for the same observation.

    It does NOT diagnose crop problems.

    Examples:

        NDVI:
            unusually low relative to field

        NDMI:
            unusually low relative to field

        BSI:
            unusually high relative to field

        NDWI:
            unusually low or high relative to field
    """

    metric_type = metric_type.strip().lower()

    rule = METRIC_ANOMALY_RULES.get(metric_type)

    if rule is None:
        raise ValueError("No anomaly rule configured for " f"metric '{metric_type}'.")

    minimum_required_difference = (
        minimum_difference
        if minimum_difference is not None
        else rule.minimum_difference
    )

    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise RuntimeError(f"{metric_type.upper()} raster " "has no CRS.")

        if not src.crs.is_projected:
            raise RuntimeError(
                f"{metric_type.upper()} raster "
                "must use a projected CRS for "
                "area calculation."
            )

        raster = src.read(
            1,
            masked=True,
        ).astype(np.float32)

        data = raster.filled(np.nan)

        masked = np.ma.getmaskarray(raster)

        # Do NOT restrict values to [-1, 1].
        #
        # RECI, MCARI, EVI2 and other metrics are not all
        # guaranteed to lie inside the normalized-difference
        # range.
        #
        # The generic metric processor is responsible for
        # producing valid masked raster values.

        valid = ~masked & np.isfinite(data)

        valid_values = data[valid]

        valid_pixel_count = int(valid.sum())

        if valid_pixel_count < min_field_pixels:
            return AnomalyDetectionResult(
                zones=[],
                analysis={
                    "status": ("insufficient_pixels"),
                    "method": ("robust_mad_metric_v1"),
                    "metric_type": metric_type,
                    "direction": (rule.direction),
                    "valid_pixel_count": (valid_pixel_count),
                    "minimum_required": (min_field_pixels),
                    "zone_count": 0,
                },
            )

        field_mean = float(np.mean(valid_values))

        field_median = float(np.median(valid_values))

        mad = float(np.median(np.abs(valid_values - field_median)))

        robust_sigma = 1.4826 * mad

        absolute_requirement = minimum_required_difference

        relative_requirement = abs(field_median) * relative_difference_fraction

        variability_requirement = robust_sigma * robust_sigma_factor

        required_difference = max(
            absolute_requirement,
            relative_requirement,
            variability_requirement,
        )

        candidate_groups = _build_candidate_masks(
            rule=rule,
            data=data,
            valid=valid,
            field_median=field_median,
            required_difference=(required_difference),
        )

        structure = np.ones(
            (
                3,
                3,
            ),
            dtype=np.uint8,
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

        raw_component_count = 0

        candidate_pixel_count = 0

        candidate_counts: dict[
            str,
            int,
        ] = {}

        component_counts: dict[
            str,
            int,
        ] = {}

        for (
            anomaly_type,
            threshold,
            candidate_mask,
        ) in candidate_groups:
            directional_candidate_count = int(candidate_mask.sum())

            candidate_counts[anomaly_type] = directional_candidate_count

            candidate_pixel_count += directional_candidate_count

            (
                component_labels,
                component_count,
            ) = label(
                candidate_mask,
                structure=structure,
            )

            component_counts[anomaly_type] = int(component_count)

            raw_component_count += int(component_count)

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

                zone_max = float(np.max(component_values))

                difference = zone_mean - field_median

                absolute_difference = abs(difference)

                if abs(field_median) > 0.05:
                    percent_difference = difference / abs(field_median) * 100.0
                else:
                    percent_difference = None

                if robust_sigma > 1e-9:
                    robust_z = absolute_difference / robust_sigma
                else:
                    robust_z = None

                if required_difference > 1e-9:
                    deviation_ratio = absolute_difference / required_difference
                else:
                    deviation_ratio = 0.0

                raster_polygons = []

                for (
                    geometry_json,
                    value,
                ) in shapes(
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
                    robust_z=robust_z,
                    deviation_ratio=(deviation_ratio),
                )

                zone_counter += 1

                zones.append(
                    AnomalyZone(
                        zone_index=(zone_counter),
                        anomaly_type=(anomaly_type),
                        severity=severity,
                        pixel_count=(component_pixel_count),
                        area_sqm=(area_sqm),
                        area_acres=(area_sqm / SQM_PER_ACRE),
                        zone_mean_value=(zone_mean),
                        zone_min_value=(zone_min),
                        zone_max_value=(zone_max),
                        field_mean_value=(field_mean),
                        field_median_value=(field_median),
                        threshold_value=(threshold),
                        difference_from_field=(difference),
                        percent_difference=(percent_difference),
                        geometry=mapping(zone_multi),
                        metadata_json={
                            "metric_type": (metric_type),
                            "direction": (rule.direction),
                            "anomaly_type": (anomaly_type),
                            "touches_nodata": (touches_nodata),
                            "absolute_difference": (absolute_difference),
                            "robust_z": (robust_z),
                            "deviation_ratio": (deviation_ratio),
                            "required_difference": (required_difference),
                        },
                    )
                )

        low_threshold = field_median - required_difference

        high_threshold = field_median + required_difference

        analysis = {
            "status": "completed",
            "method": ("robust_mad_metric_v1"),
            "metric_type": (metric_type),
            "metric_label": (rule.label),
            "direction": (rule.direction),
            "field_mean": (field_mean),
            "field_median": (field_median),
            "mad": mad,
            "robust_sigma": (robust_sigma),
            "minimum_difference": (minimum_required_difference),
            "relative_difference_fraction": (relative_difference_fraction),
            "robust_sigma_factor": (robust_sigma_factor),
            "absolute_requirement": (absolute_requirement),
            "relative_requirement": (relative_requirement),
            "variability_requirement": (variability_requirement),
            "required_difference": (required_difference),
            "low_threshold": (low_threshold),
            "high_threshold": (high_threshold),
            "valid_pixel_count": (valid_pixel_count),
            "candidate_pixel_count": (candidate_pixel_count),
            "candidate_counts": (candidate_counts),
            "raw_component_count": (raw_component_count),
            "component_counts": (component_counts),
            "min_cluster_pixels": (min_cluster_pixels),
            "zone_count": (len(zones)),
        }

        return AnomalyDetectionResult(
            zones=zones,
            analysis=analysis,
        )
