"""Quality-gated descriptive optical/radar comparisons and stage-aware context.

This deliberately produces observations, not diagnosis, predicted yield,
automatic fertilizer advice or calibrated radar anomaly alerts.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite

from app.schemas.satellite_trends import SatelliteTrendPoint


METRIC_UNITS = {
    "sar_vv_db": "dB", "sar_vh_db": "dB", "sar_rvi": "index",
    "ndvi": "index", "ndmi": "index", "ndre": "index",
}
OPTICAL = ("ndvi", "ndmi", "ndre")
RADAR = ("sar_vh_db", "sar_vv_db", "sar_rvi")


def quality_ok(point: SatelliteTrendPoint) -> bool:
    return (
        point.median is not None and isfinite(point.median)
        and point.valid_pixel_percent is not None
        and isfinite(point.valid_pixel_percent)
        and point.valid_pixel_percent >= 80
    )


def descriptive_pair(points: list[SatelliteTrendPoint]) -> dict | None:
    """Two distinct quality-screened acquisition dates, never same-day repeats."""
    valid = sorted((p for p in points if quality_ok(p)),
                   key=lambda p: (p.observed_on, str(p.observation_id)), reverse=True)
    if not valid:
        return None
    latest = valid[0]
    older = next((p for p in valid[1:] if p.observed_on < latest.observed_on), None)
    return {
        "status": "complete" if older is not None else "one_usable_date",
        "metric_type": latest.metric_type,
        "source": latest.source,
        "unit": METRIC_UNITS.get(latest.metric_type, "index"),
        "orbit_key": latest.radar_orbit_key,
        "latest_date": latest.observed_on.isoformat(),
        "latest_value": round(latest.median, 4),
        "latest_valid_percent": round(latest.valid_pixel_percent, 1),
        "previous_date": older.observed_on.isoformat() if older else None,
        "previous_value": round(older.median, 4) if older else None,
        "days_between": (latest.observed_on - older.observed_on).days if older else None,
        "change": round(latest.median - older.median, 4) if older else None,
        "interpretation": "Numerical change only; not evidence of disease, water deficit or crop health.",
    }


def build_field_comparisons(points: list[SatelliteTrendPoint]) -> dict:
    groups: dict[tuple[str, str, str], list[SatelliteTrendPoint]] = defaultdict(list)
    blocked_radar = 0
    for p in points:
        if p.metric_type in RADAR and p.source.startswith("sentinel-1"):
            if not p.radar_orbit_key:
                blocked_radar += 1
                continue
            groups[("radar", p.radar_orbit_key, p.metric_type)].append(p)
        elif p.metric_type in OPTICAL and p.source.startswith("sentinel-2"):
            groups[("optical", p.source, p.metric_type)].append(p)

    comparisons = []
    for (kind, _, _), entries in sorted(groups.items()):
        pair = descriptive_pair(entries)
        if pair:
            comparisons.append({**pair, "kind": kind})
    comparisons.sort(key=lambda x: (x["kind"], x["latest_date"]), reverse=True)
    return {
        "comparisons": comparisons,
        "suppressed_unidentified_radar_metrics": blocked_radar,
        "notes": [
            "Same-orbit radar only; Sentinel-1 ascending and descending passes are not mixed.",
            "At least 80% valid field coverage is required for each compared metric.",
            "Two-pass changes remain available without farmer-confirmed growth stages; existing conservative screening gates are unchanged.",
        ],
    }


STAGE_INDICES = {
    "planting": ("savi", "msavi", "bsi"),
    "emergence": ("savi", "msavi", "ndvi"),
    "establishment": ("savi", "msavi", "ndvi"),
    "vegetative": ("ndvi", "ndre", "ndmi"),
    "stem_elongation": ("ndvi", "ndre", "ndmi"),
    "panicle": ("ndre", "ndmi", "ndvi"),
    "heading": ("ndre", "ndmi", "ndvi"),
    "tasseling": ("ndre", "ndmi", "ndvi"),
    "silking": ("ndre", "ndmi", "ndvi"),
    "flowering": ("ndre", "ndmi", "ndvi"),
    "grain_fill": ("ndre", "ndmi", "ndvi"),
    "fruiting": ("ndre", "ndmi", "ndvi"),
    "maturity": ("ndmi", "ndvi", "bsi"),
}
STAGE_NOTES = {
    "planting": "Soil background may dominate optical vegetation indices.",
    "emergence": "Low canopy cover makes soil-adjusted indices worth comparing.",
    "establishment": "Soil and water background may dominate immature canopy signals.",
    "vegetative": "NDVI tracks relative green canopy; NDRE can add chlorophyll-sensitive context.",
    "panicle": "Red-edge and canopy moisture signals can be compared, but are not nutrient tests.",
    "heading": "Avoid assuming a natural stage transition is crop stress.",
    "grain_fill": "Expected ripening may reduce greenness and moisture indices.",
    "maturity": "Senescence and canopy drying are expected in many annual crops.",
}


def indices_for_stage(stage_code: str | None, crop_profile_key: str) -> dict:
    if crop_profile_key in {"mango", "litchi", "guava", "sapota"}:
        return {
            "recommended_indices": ["ndvi", "ndre", "ndmi"],
            "guidance": "Perennial tree canopy and understory change throughout the year; interpretation requires observed flowering, fruiting and pruning context.",
        }
    if crop_profile_key == "other":
        return {
            "recommended_indices": [],
            "guidance": "Crop-specific index guidance unavailable; manually record stages and ground observations.",
        }
    return {
        "recommended_indices": list(STAGE_INDICES.get(stage_code, ("ndvi", "ndmi"))),
        "guidance": STAGE_NOTES.get(
            stage_code, "Satellite indices are indirect canopy signals; verify observations in the field."
        ),
    }
