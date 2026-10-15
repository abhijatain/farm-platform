"""Versioned, explicitly provisional crop-stage milestone templates.

Days after planting are broad illustrative milestones, NOT a validated
phenology model or a diagnosis. Calibrate by location, cultivar and GDD
before enabling agronomic/health decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CropStage:
    code: str
    label: str
    approx_day: int | None


@dataclass(frozen=True)
class CropProfile:
    key: str
    label: str
    base_temperature_c: float | None
    stages: tuple[CropStage, ...]
    provisional: bool = True
    version: str = "2026-10-v1"


def _stages(rows: tuple[tuple[str, str, int | None], ...]) -> tuple[CropStage, ...]:
    return tuple(CropStage(*row) for row in rows)


PROFILES: dict[str, CropProfile] = {
    "wheat": CropProfile(
        "wheat", "Wheat", 0.0,
        _stages((
            ("planting", "Sowing", 0),
            ("emergence", "Emergence", 8),
            ("vegetative", "Tillering", 25),
            ("stem_elongation", "Stem elongation", 58),
            ("heading", "Heading", 90),
            ("grain_fill", "Grain filling", 112),
            ("maturity", "Maturity", 138),
        )),
    ),
    "rice": CropProfile(
        "rice", "Rice", 10.0,
        _stages((
            ("planting", "Sowing / transplanting", 0),
            ("establishment", "Establishment", 12),
            ("vegetative", "Tillering", 30),
            ("panicle", "Panicle initiation", 63),
            ("heading", "Heading / flowering", 91),
            ("grain_fill", "Grain filling", 106),
            ("maturity", "Maturity", 133),
        )),
    ),
    "maize": CropProfile(
        "maize", "Maize", 10.0,
        _stages((
            ("planting", "Sowing", 0),
            ("emergence", "Emergence", 8),
            ("vegetative", "Vegetative growth", 24),
            ("tasseling", "Tasseling", 56),
            ("silking", "Silking", 65),
            ("grain_fill", "Grain filling", 84),
            ("maturity", "Maturity", 113),
        )),
    ),
}
ALIASES = {
    "gehun": "wheat", "gehu": "wheat",
    "paddy": "rice", "dhan": "rice", "chawal": "rice",
    "corn": "maize", "makka": "maize", "makkai": "maize",
}
GENERIC = CropProfile(
    "other", "Other / uncalibrated crop", None,
    _stages((
        ("planting", "Planting / starting", None),
        ("establishment", "Establishment", None),
        ("vegetative", "Vegetative growth", None),
        ("flowering", "Flowering", None),
        ("fruiting", "Fruit or grain development", None),
        ("maturity", "Maturity", None),
    )),
    provisional=False,
)


def resolve_profile(crop_name: str) -> CropProfile:
    normalized = " ".join(crop_name.lower().strip().split())
    key = ALIASES.get(normalized, normalized)
    return PROFILES.get(key, GENERIC)


def provisional_stage(*, crop_name: str, planted_on: date | None, as_of: date) -> str | None:
    """No automatic phase for unknown crops or cycles missing planting dates."""
    profile = resolve_profile(crop_name)
    if not profile.provisional or planted_on is None or planted_on > as_of:
        return None
    age = (as_of - planted_on).days
    options = [stage for stage in profile.stages if stage.approx_day is not None and stage.approx_day <= age]
    return options[-1].code if options else None


def growing_degree_days(
    *,
    planted_on: date,
    as_of: date,
    base_temperature_c: float,
    daily_readings: list,
) -> tuple[float | None, int, int]:
    """Count only historical/recent modeled days with valid min and max.

    Refuse totals with gaps: missing temperatures must not be treated as zero.
    """
    total_days = (as_of - planted_on).days + 1
    if total_days <= 0:
        return (None, 0, 0)
    by_date = {
        point.date: point for point in daily_readings
        if planted_on <= point.date <= as_of and point.source != "forecast"
        and point.temperature_min_c is not None and point.temperature_max_c is not None
    }
    if len(by_date) != total_days:
        return (None, len(by_date), total_days)
    total = sum(
        max(0.0, (point.temperature_max_c + point.temperature_min_c) / 2 - base_temperature_c)
        for point in by_date.values()
    )
    return (round(total, 1), len(by_date), total_days)
