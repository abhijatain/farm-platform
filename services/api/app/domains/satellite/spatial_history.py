"""Conservative, field-relative multi-date zone evidence from stored polygons.

No raster values are invented. Repeated *below-field-baseline* detections are
candidates for scouting, never measured productivity or diagnosed crop stress.
Inputs are already projected into EPSG:3857 by the database; areas are
calibrated against the accurate field geodesic area supplied by PostGIS.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from math import atan, ceil, cos, exp, floor, log, pi, sqrt, tan
from typing import Any

from shapely.geometry import box, mapping, Polygon
from shapely.ops import unary_union, transform

EARTH_RADIUS_M = 6378137.0
ACRE_SQM = 4046.8564224
MAX_CELLS = 280
CELL_MIN_METERS = 20.0


@dataclass(frozen=True)
class Scene:
    observation_id: str
    observed_on: date
    valid_percent: float
    native_resolution_m: float
    polygons: dict[str, Any]


def _unproject_geometry(geometry: Any) -> dict:
    def convert(x, y, z=None):
        lon = (x / EARTH_RADIUS_M) * 180 / pi
        lat = (2 * atan(exp(y / EARTH_RADIUS_M)) - pi / 2) * 180 / pi
        return (lon, lat) if z is None else (lon, lat, z)
    return mapping(transform(convert, geometry))


def _area_acres(polygon: Any, projected_field_area: float, real_field_area: float) -> float:
    return round(
        polygon.area / projected_field_area * real_field_area / ACRE_SQM,
        4,
    ) if projected_field_area > 0 else 0.0


def _cell_grid(field: Any, step: float):
    min_x, min_y, max_x, max_y = field.bounds
    cols = max(1, ceil((max_x - min_x) / step))
    rows = max(1, ceil((max_y - min_y) / step))
    for row in range(rows):
        for col in range(cols):
            square = box(
                min_x + col * step, min_y + row * step,
                min_x + (col + 1) * step, min_y + (row + 1) * step,
            )
            clipped = square.intersection(field)
            if clipped.area > 0.01:
                yield clipped


def summarize_spatial_history(
    field: Any,
    field_area_sqm: float,
    scenes: list[Scene],
    *,
    history_limited: bool = False,
) -> dict:
    """Inspect sampled geospatial cells; suppress historical labels for short data.

    Stable classifications require 6 quality-checked dates in >=2 years, but
    3 dates suffice for *candidate* temporal new/persistent/resolved labeling.
    """
    projected_area = field.area
    years = sorted({scene.observed_on.year for scene in scenes})
    dates = sorted({scene.observed_on for scene in scenes}, reverse=True)
    result: dict[str, Any] = {
        "status": "insufficient_history",
        "observation_count": len(scenes),
        "year_count": len(years),
        "years": years,
        "date_range": [dates[-1].isoformat(), dates[0].isoformat()] if dates else None,
        "minimum_valid_percent": 80,
        "cell_size_m": None,
        "zone_model": "relative_anomaly_frequency_grid_v2",
        "recent_dates": [d.isoformat() for d in dates[:3]],
        "zones": [],
        "tracking": [],
        "warnings": [
            "Relative anomaly frequency does not measure productivity, soil fertility, crop health or yield."
        ],
    }
    if projected_area <= 0 or field_area_sqm <= 0:
        result["warnings"].append("Invalid field boundary area.")
        return result
    if len(scenes) < 3:
        result["warnings"].append("At least three quality-screened optical dates are needed to track zones.")
        return result

    cell_size = max(
        CELL_MIN_METERS,
        max((s.native_resolution_m for s in scenes), default=CELL_MIN_METERS),
        sqrt(projected_area / 180),
    )
    min_x, min_y, max_x, max_y = field.bounds
    while (ceil((max_x-min_x)/cell_size) * ceil((max_y-min_y)/cell_size)) > MAX_CELLS:
        cell_size *= 1.3
    result["cell_size_m"] = round(cell_size, 1)
    if projected_area / (cell_size * cell_size) < 8:
        result["warnings"].append(
            "Small field/few independent pixels: spatial zone reliability is limited."
        )
    if history_limited:
        result["warnings"].append(
            "Anomaly rows exceed the retrieval limit; zones are withheld to avoid incomplete evidence."
        )
        return result

    evidence: dict[str, list[Any]] = defaultdict(list)
    frequencies: dict[str, list[float]] = defaultdict(list)
    tracks: dict[str, list[Any]] = defaultdict(list)
    recent_dates = dates[:3]
    latest = recent_dates[0]
    stable_enough = len(scenes) >= 6 and len(years) >= 3
    for cell in _cell_grid(field, cell_size):
        appearances: dict[str, list[date]] = {"below_field_baseline": [], "above_field_baseline": []}
        for scene in scenes:
            for anomaly_type in appearances:
                poly = scene.polygons.get(anomaly_type)
                if poly is not None and not poly.is_empty and poly.intersects(cell):
                    # Require an appreciable affected share instead of a sliver crossing.
                    if poly.intersection(cell).area / cell.area >= 0.20:
                        appearances[anomaly_type].append(scene.observed_on)
        for anomaly_type, hits in appearances.items():
            count = len(hits)
            if count == 0:
                continue
            frequency = count / len(scenes)
            # Historical zone candidates are only shown for multi-year evidence.
            if stable_enough and frequency >= 0.35:
                label = "repeated_relative_low" if anomaly_type == "below_field_baseline" else "repeated_relative_high"
                key = f"{label}:{'persistent' if frequency >= 0.6 else 'variable'}"
                evidence[key].append(cell)
                frequencies[key].append(frequency)
            if len(scenes) >= 3:
                active_now = latest in hits
                earlier_recent_count = sum(day in hits for day in recent_dates[1:])
                if active_now and earlier_recent_count == len(recent_dates) - 1:
                    status = "persistent"
                elif active_now and earlier_recent_count:
                    status = "recurring"
                elif active_now:
                    status = "new"
                elif earlier_recent_count:
                    status = "resolved"
                else:
                    status = "historical"
                # Only classify zones using the three most recent qualifying dates.
                if status != "historical":
                    tracks[f"{anomaly_type}:{status}"].append(cell)
    for key, cells in sorted(evidence.items()):
        merged = unary_union(cells)
        label, persistence = key.split(":")
        result["zones"].append({
            "id": key,
            "classification": label,
            "stability": persistence,
            "stability_score": round(sum(frequencies[key]) / len(frequencies[key]), 3),
            "centroid": _unproject_geometry(merged.centroid)["coordinates"],
            "visit_point": _unproject_geometry(merged.representative_point())["coordinates"],
            "area_acres": _area_acres(merged, projected_area, field_area_sqm),
            "geometry": _unproject_geometry(merged),
            "interpretation": "Repeated field-relative signal; candidate scouting/soil sample zone, not yield.",
        })
    for key, cells in sorted(tracks.items()):
        merged = unary_union(cells)
        anomaly_type, status = key.split(":")
        result["tracking"].append({
            "id": key,
            "anomaly_type": anomaly_type,
            "transition": status,
            "area_acres": _area_acres(merged, projected_area, field_area_sqm),
            "geometry": _unproject_geometry(merged),
            "recent_dates": result["recent_dates"],
        })
    if stable_enough:
        result["status"] = "candidate_zones"
        result["warnings"].append(
            "Only years with ingested, comparable Sentinel-2 scenes are represented; historical sampling may be biased."
        )
    else:
        result["status"] = "short_history"
        result["warnings"].append(
            "Historical management zones require at least six optical observations across three calendar years. No stable productivity map is inferred."
        )
    return result
