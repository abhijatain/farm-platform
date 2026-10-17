"""Deterministic, explicitly fictional crop diary for a one-field UI demo.

Never use these values as observed harvests, verified growth stages, or
agronomic instructions. Satellite indices are references to REAL ingestion
sources, not generated measurements. One physical field, four crop cycles.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class DemoCrop:
    label: str
    season_name: str
    season_type: str
    started_on: date
    planted_on: date
    harvested_on: date
    crop: str
    variety: str
    # Sample values are fictional, per acre, and identified as such.
    example_yield_kg_per_acre: float


CROPS = (
    DemoCrop("Wheat 2025", "Rabi 2024–25", "rabi",
        date(2024, 10, 25), date(2024, 11, 15), date(2025, 4, 10),
        "wheat", "Demo wheat variety", 1700),
    DemoCrop("Rice 2025", "Kharif 2025", "kharif",
        date(2025, 5, 25), date(2025, 6, 10), date(2025, 10, 12),
        "rice", "Demo paddy variety", 2250),
    DemoCrop("Wheat 2026", "Rabi 2025–26", "rabi",
        date(2025, 11, 1), date(2025, 11, 16), date(2026, 4, 12),
        "wheat", "Demo wheat variety", 1750),
    DemoCrop("Rice 2026", "Kharif 2026", "kharif",
        date(2026, 5, 24), date(2026, 6, 8), date(2026, 10, 12),
        "rice", "Demo paddy variety", 2300),
)

# (time relative to first preparation vs sowing, day offset, activity,
#  purpose, satellite context). No chemical names, rates, health claims,
#  field sensor values or planting dates are presented as real.
WHEAT_PREPARATION = (
    (-0, "soil_sampling", "Collect soil sample; demonstration record.", ("bsi",)),
    (2, "residue_management", "Clear prior crop residues; demo operation.", ("bsi",)),
    (4, "tillage", "Tractor cultivation; demo operation.", ("bsi",)),
    (6, "harrowing", "Break clods using harrow; demo operation.", ("bsi",)),
    (9, "leveling", "Level field for sowing; demo operation.", ("bsi",)),
    (12, "pre_sowing_irrigation", "Pre-sowing irrigation; demo record.", ("ndmi", "lst_c")),
    (15, "seed_selection", "Select seed lot; fictional diary entry.", ("bsi",)),
    (17, "seed_treatment", "Seed preparation and treatment, with no product/dose recorded.", ("bsi",)),
)
RICE_PREPARATION = (
    (0, "soil_sampling", "Take pre-season soil sample; demo record.", ("bsi",)),
    (2, "residue_management", "Clear/recycle preceding crop straw; demo record.", ("bsi",)),
    (4, "tillage", "Tractor preparation; demo record.", ("bsi",)),
    (6, "leveling", "Level and prepare plot; demo record.", ("bsi",)),
    (8, "bunding", "Repair water-control bunds; demo record.", ("bsi",)),
    (10, "irrigation", "Wet field during land preparation; demo record.", ("ndmi", "sar_rvi")),
    (12, "puddling", "Wet rice field preparation; demo record.", ("ndmi", "sar_rvi")),
    (14, "nursery_preparation", "Prepare rice seedlings for transplanting; fictional entry.", ("ndvi",)),
)

# Offsets below are relative to *planting*; never after that crop's harvest.
# These are examples of categories the platform can record, not a required
# spray, irrigation, or fertilizer schedule.
WHEAT_GROWTH = (
    (0, "sowing", "Seed drilled/sown; sample planting record.", ("bsi",)),
    (2, "basal_fertilizer", "Sample basal nutrition record (no rate given).", ("ndre",)),
    (9, "emergence_check", "Inspect emerged seedlings, demo observation.", ("ndvi",)),
    (15, "irrigation", "Illustrative irrigation event.", ("ndmi", "lst_c")),
    (22, "weed_scouting", "Observe weeds before deciding on control.", ("ndvi",)),
    (27, "weeding", "Demo manual/mechanical weed management.", ("ndvi",)),
    (34, "fertilizer", "Sample top-dressing activity (no dose).", ("ndre",)),
    (40, "irrigation", "Illustrative follow-up irrigation.", ("ndmi",)),
    (47, "pest_scouting", "Observe insects; sample scouting record.", ("ndvi",)),
    (53, "herbicide", "Hypothetical weed treatment; no chemical or rate provided.", ("ndvi",)),
    (63, "fungicide", "Hypothetical disease response; not evidence of disease.", ("ndvi", "ndre")),
    (70, "irrigation", "Illustrative irrigation event.", ("ndmi",)),
    (79, "canopy_inspection", "Sample canopy and colour survey.", ("ndvi", "ndre")),
    (90, "heading_inspection", "Inspect heading in field; sample record.", ("ndvi", "ndre")),
    (99, "pesticide", "Hypothetical insect treatment; no product or rate.", ("ndvi",)),
    (112, "grain_filling_check", "Sample grain development inspection.", ("ndvi", "ndmi")),
    (124, "irrigation", "Sample last irrigation decision event.", ("ndmi",)),
    (133, "maturity_check", "Sample pre-harvest maturity assessment.", ("ndvi", "bsi")),
)
RICE_GROWTH = (
    (0, "transplanting", "Rice seedlings transplanted; sample planting record.", ("sar_rvi", "ndmi")),
    (3, "gap_filling", "Fill missing plants; demo event.", ("ndvi",)),
    (8, "irrigation", "Illustrative water management.", ("sar_rvi", "ndmi")),
    (15, "basal_fertilizer", "Sample nutrient management; no dose.", ("ndre",)),
    (24, "weeding", "Illustrative manual/mechanical weeding.", ("ndvi",)),
    (31, "tillering_inspection", "Demo tillering inspection.", ("ndvi", "ndre")),
    (38, "irrigation", "Illustrative water-control inspection.", ("sar_rvi", "ndmi")),
    (44, "fertilizer", "Sample crop nutrition application; no rate.", ("ndre",)),
    (50, "pest_scouting", "Observe insects before treatment.", ("ndvi",)),
    (56, "pesticide", "Hypothetical pest treatment; no product or rate.", ("ndvi",)),
    (62, "disease_scouting", "Sample disease scouting (not diagnosis).", ("ndvi", "ndre")),
    (68, "fungicide", "Hypothetical fungicide event; no product or rate.", ("ndvi",)),
    (74, "panicle_initiation_check", "Sample panicle initiation check.", ("ndre", "ndvi")),
    (83, "irrigation", "Illustrative water management.", ("sar_rvi", "ndmi")),
    (94, "flowering_inspection", "Demo heading and flowering inspection.", ("ndvi", "ndre")),
    (103, "canopy_inspection", "Sample canopy monitoring.", ("ndvi", "ndmi")),
    (112, "grain_filling_check", "Sample grain-filling inspection.", ("ndvi",)),
    (119, "drainage", "Illustrative pre-harvest water withdrawal.", ("sar_rvi", "bsi")),
)
POSTHARVEST = (
    (1, "threshing", "Sample grain separation event.", ("bsi",)),
    (2, "drying", "Sample post-harvest grain drying record.", ("bsi",)),
    (4, "grading", "Sample grain grading and cleaning.", ("bsi",)),
    (5, "storage", "Sample bagging and storage record.", ("bsi",)),
    (7, "transport", "Sample transport to market/storage.", ("bsi",)),
    (9, "sale", "Fictional sale/settlement entry; no actual price.", ("bsi",)),
)


@dataclass(frozen=True)
class PlannedActivity:
    activity_type: str
    occurred_on: date
    notes: str
    satellite_metrics: tuple[str, ...]


def plan_activities(crop: DemoCrop) -> list[PlannedActivity]:
    pre = WHEAT_PREPARATION if crop.crop == "wheat" else RICE_PREPARATION
    steps = WHEAT_GROWTH if crop.crop == "wheat" else RICE_GROWTH
    rows = [
        PlannedActivity(kind, crop.started_on + timedelta(days=offset), note, metrics)
        for offset,kind,note,metrics in pre
    ]
    rows += [
        PlannedActivity(kind,crop.planted_on + timedelta(days=offset),note,metrics)
        for offset,kind,note,metrics in steps
        if crop.planted_on + timedelta(days=offset) < crop.harvested_on
    ]
    rows.append(PlannedActivity("harvest",crop.harvested_on,
        "Fictional harvest and yield for demonstration; NOT measured.",("ndvi","bsi")))
    rows += [
        PlannedActivity(kind,crop.harvested_on + timedelta(days=offset),note,metrics)
        for offset,kind,note,metrics in POSTHARVEST
    ]
    return sorted(rows,key=lambda x:x.occurred_on)


def activity_timestamp(day:date) -> datetime:
    """Save offset-aware 10:00 Indian farm local time, not midnight UTC."""
    return datetime.combine(day,time(10,0),tzinfo=IST)


def satellite_date_windows(crops= CROPS) -> list[tuple[date,date,str]]:
    """Four independent source acquisition windows; job deduped by crop label."""
    return [(c.started_on,c.harvested_on,c.label) for c in crops]


def validate_demo_plan() -> None:
    assert len(CROPS)==4
    assert {(c.crop,c.label.split()[-1]) for c in CROPS} == {
        ("wheat","2025"),("rice","2025"),("wheat","2026"),("rice","2026")
    }
    assert all(c.started_on < c.planted_on < c.harvested_on for c in CROPS)
    for i,c in enumerate(CROPS):
        if i: assert CROPS[i-1].harvested_on < c.started_on
        items=plan_activities(c)
        assert len(items)>=25
        assert items[0].occurred_on >= c.started_on
        assert all(item.satellite_metrics for item in items)
        assert sum(item.activity_type in ("sowing","transplanting") for item in items)==1
        assert sum(item.activity_type=="harvest" for item in items)==1
