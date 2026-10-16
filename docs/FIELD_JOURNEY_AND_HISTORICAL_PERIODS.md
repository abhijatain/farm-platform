# Farmer workflow: field → crop journey → historical comparisons

This document specifies the farmer-facing workflow added in PR #19.

## Data model: one meaning per thing

- **User**: verifies their phone with Firebase and owns farms.
- **Farm**: administrative unit with its own fields and farm seasons.
- **Field**: a geospatial polygon reused over successive crop cycles.
- **Season**: the farm's Kharif/Rabi/other organizational period.
- **CropCycle**: the crop selected for one field and its actual agricultural
  timeline: `started_on` (first preparation / management period),
  optional `planted_on`, optional `expected_harvest_on`,
  and (once finished) `harvested_on` and measured yield.
- **Activity**: the real operation the farmer did, with local date/time,
  field ID and selected crop-cycle ID. Tractor/tillage may precede planting.
  `sowing` and `transplanting` establish the planting date if none
  was recorded. A later conflicting planting date requires explicit correction.
- **Growth-stage observation**: stage the farmer has actually seen. If no
  observation is available, a provisional crop-stage template may be shown,
  clearly labeled an estimate. Unknown crops receive no made-up stages.
- **Historical window**: a **separate stored analysis**, not a second
  `CropCycle`. The user chooses Aug–Oct, Nov–Jan, or the crop-cycle calendar
  and which earlier years to include. Results remain keyed by field, crop,
  calendar period and year in the existing seasonal-composites table.

## A typical journey

1. Farmer signs in with a real phone number.
2. Creates/selects a farm, season and field boundary.
3. Opens field → **Journey** → **Start crop**. Example: Rice PR-126;
   preparation/start date October 10. Planting date can be left empty.
4. Records tractor/tillage on October 10, leveling October 12, then a
   sowing/transplanting activity October 16. Only then does crop age begin;
   preparation lasted 6 days from first tillage to planting.
5. Optionally enters an **expected harvest date**. The dashboard computes
   days left using the farmer's plan. It does not predict an unentered date.
6. Journey displays current stage (farmer-confirmed first, otherwise
   provisional), crop age, recorded preparation duration and the activity
   diary. The farmer can enter new activities and correct dates.
7. **Satellite → Trends** defaults to the same crop cycle's
   `started_on` through today (or actual harvest for finished cycles),
   capturing preparation and all subsequent measurements. Each metric stays
   its own source/signal; clouds and missing data are not filled.
8. Farmer records harvest and measured yield, closing that crop cycle.
   They can start another, retaining old crop-cycle timelines.
9. **Historical Zones** asks which crop reference and calendar period
   to compare. Choose e.g. August–October and 2020–2025, then click
   **Calculate** explicitly. The worker streams remote Sentinel-2 samples,
   saves only the compact final yearly seasonal mean and discards raw source
   windows. Choose completed years to combine and compare individual maps.
10. Later, choose November–January for another separate saved historical
    analysis. These reports do not imply a new crop was planted.

## Dates and trust

The browser sends offset-aware timestamps preserving the farmer's *civil
date* (e.g. 00:30 +05:30 on October 16 stays an October 16 planting event
even though the corresponding UTC instant is October 15). Harvest and
planting dates are not silently overwritten by a conflicting second record.

Days-to-harvest and stage calendars are **planning context**, not evidence
of physiological maturity or guarantees of yield. A crop without a planted
date shows **Not planted** and no fabricated age.

Only authorized field/crop-cycle owners can update plans, record activities
or create historical reports.

## Verification

- API migration: **none** in PR #19; existing tables are reused.
- End-to-end manual flow: test Farm → Season → Field → Journey → crop
  preparation → planting at 00:30 India time → activity diary → age and
  stage update → crop graph time window → expected harvest → measured
  harvest → historical month period A and period B → recall saved result.
- All four CI checks (web build/lint, API/PostGIS, satellite-worker, tiler)
  should be green before merge.
- Production release is a separate step and requires HTTPS, private tile
  authorization, production secrets and real backups. Local ngrok/Vite is
  not a production deployment.
