"""Nonpersistent robust contrast and zone metrics for cached NDVI composites.

Display contrast is separate from agronomic evidence, and is NOT yield.
"""
from __future__ import annotations

from math import ceil, floor, isfinite
from typing import Any

MIN_SPREAD = 0.035
MIN_ZONE_DIFFERENCE = 0.02
ACRE_SQM = 4046.8564224


def _percentile(values: list[float], fraction: float) -> float:
    vals = sorted(values)
    if not vals:
        return 0.0
    index = fraction * (len(vals) - 1)
    low, high = floor(index), ceil(index)
    if low == high:
        return vals[low]
    return vals[low] * (high - index) + vals[high] * (index - low)


def _pixel_area_acres(grid: dict[str, Any]) -> float:
    transform = grid.get("transform")
    if not transform or len(transform) < 6:
        return 0.0
    a, b, _, d, e, _ = map(float, transform[:6])
    return abs(a * e - b * d) / ACRE_SQM


def describe_zone_grid(grid: dict[str, Any],
                       *, relative_pixels: list[float | None] | None = None) -> dict:
    """Derive continuous color stretch and qualified zones without changing saved data."""
    pixels = relative_pixels if relative_pixels is not None else grid["pixels"]
    mask = grid["mask"]
    n = grid["width"] * grid["height"]
    if len(pixels) != n or len(mask) != n:
        raise ValueError("Incompatible grid pixel/mask lengths")
    valid = [float(value) for value, inside in zip(pixels, mask)
             if inside and value is not None and isfinite(float(value))]
    if not valid:
        return {"status": "insufficient_data", "display": None, "zones": None,
                "zone_classes": [None] * n, "notes": ["No valid field pixels."]}
    mean = sum(valid) / len(valid)
    relative = [x - mean for x in valid]
    q10, q33, q67, q90 = (_percentile(relative, q) for q in (.1, .33, .67, .9))
    spread = q90 - q10
    meaningful = len(valid) >= 8 and spread >= MIN_SPREAD
    lo, hi = _percentile(valid, .05), _percentile(valid, .95)
    pad = max(0.0, .06 - (hi - lo)) / 2
    low_bound, high_bound = min(-MIN_ZONE_DIFFERENCE, q33), max(MIN_ZONE_DIFFERENCE, q67)
    classes: list[str | None] = []
    counts = {"low": 0, "medium": 0, "high": 0}
    for raw, inside in zip(pixels, mask):
        if not inside or raw is None or not isfinite(float(raw)):
            classes.append(None)
            continue
        deviation = float(raw) - mean
        label = ("low" if deviation <= low_bound else
                 "high" if deviation >= high_bound else "medium")
        if not meaningful:
            label = "medium"
        classes.append(label)
        counts[label] += 1
    area = _pixel_area_acres(grid)
    count = sum(counts.values())
    zones = {
        "method": "field_relative_robust_quantiles_v1",
        "status": "qualified" if meaningful else "low_spatial_contrast",
        "mapped_area_acres": round(count * area, 3),
        "low_area_acres": round(counts["low"] * area, 3),
        "medium_area_acres": round(counts["medium"] * area, 3),
        "high_area_acres": round(counts["high"] * area, 3),
        "low_percent": round(100 * counts["low"] / count, 1),
        "medium_percent": round(100 * counts["medium"] / count, 1),
        "high_percent": round(100 * counts["high"] / count, 1),
        "p10_p90_spread": round(spread, 4),
        "threshold_low": round(mean + low_bound, 4) if meaningful else None,
        "threshold_high": round(mean + high_bound, 4) if meaningful else None,
    }
    notes = [
        "Continuous color shows relative NDVI contrast, not yield.",
        "Statistics withheld when p10-p90 range is under 0.035 NDVI or fewer than eight valid cells.",
    ]
    if not meaningful:
        notes.append("Spatial variation is too small to confidently designate low/high zones.")
    return {
        "status": "zones_available" if meaningful else "low_spatial_contrast",
        "display": {"min": round(lo - pad, 5), "max": round(hi + pad, 5),
                    "mean": round(mean, 5), "mode": "robust_continuous_ndvi"},
        "zones": zones,
        "zone_classes": classes,
        "notes": notes,
    }


def combine_deviations(grids: list[dict], mask: list[bool]):
    """Equal-season-weight, per-year field-centered deviations and agreement."""
    n = len(mask)
    centers = []
    for grid in grids:
        usable = [float(v) for v, m in zip(grid["pixels"], mask)
                  if m and v is not None and isfinite(float(v))]
        centers.append(sum(usable) / len(usable) if usable else None)
    relatives: list[float | None] = []
    contributing: list[int] = []
    stable: list[bool | None] = []
    for i in range(n):
        deltas = [float(g["pixels"][i]) - center
                  for g, center in zip(grids, centers)
                  if center is not None and g["pixels"][i] is not None
                  and isfinite(float(g["pixels"][i]))]
        enough = mask[i] and len(deltas) >= max(2, (len(grids) + 1) // 2)
        contributing.append(len(deltas))
        relatives.append(round(sum(deltas) / len(deltas), 5) if enough else None)
        if not enough or len(grids) < 3 or len(deltas) < 3:
            stable.append(None)
        else:
            above = sum(delta >= MIN_ZONE_DIFFERENCE for delta in deltas)
            below = sum(delta <= -MIN_ZONE_DIFFERENCE for delta in deltas)
            stable.append(max(above, below) / len(deltas) >= .75)
    return relatives, contributing, stable
