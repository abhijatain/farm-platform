"""Explicit manual worker for seasonal Sentinel-2 NDVI means (no scene persistence).

Run: uv run python -m satellite_worker.ingestion.seasonal_zones --once/--loop

A database row is created ONLY by the user's Calculate action. Remote COGs
are read in field-sized windows, processed in memory, and discarded per pass.
Only a compact 64x64 mean grid persists in PostgreSQL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform
from sqlalchemy import text

from satellite_worker.persistence.connection import engine
from satellite_worker.sources.sentinel2.grid import (
    build_analysis_grid, read_scl, read_spectral_band, build_scene_valid_mask,
)
from satellite_worker.sources.sentinel2.reflectance import to_reflectance
from satellite_worker.sources.sentinel2.indices import calculate_metric
from satellite_worker.sources.stac import search_sentinel2

LOG = logging.getLogger(__name__)
WIDTH = 64
HEIGHT = 64
MAX_SCENES = 18
MIN_SCENES = 3
MIN_COVERAGE = 80.0
NODATA = -9999.0

def canonical_grid(geometry):
    geom = shape(geometry)
    lon, lat = geom.centroid.x, geom.centroid.y
    zone = max(1, min(60, int((lon + 180) / 6) + 1))
    crs = CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)
    projected = shapely_transform(
        Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform, geom
    )
    left, bottom, right, top = projected.bounds
    if right <= left or top <= bottom:
        raise ValueError("Invalid projected field boundary")
    transform = from_bounds(left, bottom, right, top, WIDTH, HEIGHT)
    mask = geometry_mask([mapping(projected)], (HEIGHT, WIDTH), transform,
                         invert=True, all_touched=False)
    if mask.sum() < 16:
        raise ValueError("Field has fewer than 16 aligned cells; insufficient spatial resolution")
    return crs, transform, mask

def select_scenes(items, start_date):
    """One best cloud-quality scene per ~10 day window, capped."""
    buckets = {}
    for item in items:
        if item.datetime is None:
            continue
        bucket = (item.datetime.date() - start_date).days // 10
        if bucket < 0:
            continue
        cloud = float(item.properties.get("eo:cloud_cover") if item.properties.get("eo:cloud_cover") is not None else 100)
        current = buckets.get(bucket)
        if current is None or cloud < current[0]:
            buckets[bucket] = (cloud, item)
    return [p[1] for _, p in sorted(buckets.items())][:MAX_SCENES]

def compute_season(geometry, start, end):
    crs, aligned_transform, inside = canonical_grid(geometry)
    items = search_sentinel2(
        geometry=geometry, start_date=start, end_date=end,
        max_scene_cloud=55, limit=0, include_cloudy=False,
    )
    scenes = select_scenes(items, start)
    if not scenes:
        raise ValueError("No suitable historical Sentinel-2 scenes found for this season.")
    summed = np.zeros((HEIGHT, WIDTH), dtype=np.float64)
    counts = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)
    used_dates = []
    failures = 0
    for item in scenes:
        try:
            grid = build_analysis_grid(item=item, field_geometry=geometry)
            if grid.pixel_count < 8:
                continue
            scl = read_scl(item=item, grid=grid)
            red = read_spectral_band(item=item, grid=grid, band_name="red")
            nir = read_spectral_band(item=item, grid=grid, band_name="nir")
            valid = build_scene_valid_mask(grid=grid, scl=scl, bands=[red, nir])
            if valid.sum() / grid.pixel_count * 100 < MIN_COVERAGE:
                continue
            red_ref, _ = to_reflectance(item=item, asset=red.asset, data=red.data)
            nir_ref, _ = to_reflectance(item=item, asset=nir.asset, data=nir.data)
            metric, physical = calculate_metric(
                metric_type="ndvi", reflectance={"red": red_ref, "nir": nir_ref}
            )
            valid &= physical
            if valid.sum() / grid.pixel_count * 100 < MIN_COVERAGE:
                continue
            masked = np.where(valid, metric, NODATA).astype("float32")
            projected = np.full((HEIGHT, WIDTH), NODATA, dtype="float32")
            reproject(
                source=masked, destination=projected,
                src_transform=grid.transform, src_crs=grid.crs, src_nodata=NODATA,
                dst_transform=aligned_transform, dst_crs=crs, dst_nodata=NODATA,
                resampling=Resampling.nearest,
            )
            good = inside & np.isfinite(projected) & (projected != NODATA)
            if good.sum() < 12:
                continue
            summed[good] += projected[good]
            counts[good] += 1
            used_dates.append(item.datetime.date().isoformat())
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            failures += 1
            LOG.warning("Skipped historical scene %s: %s", item.id, type(exc).__name__)
    if len(used_dates) < MIN_SCENES:
        raise ValueError(
            f"Only {len(used_dates)} valid dates found; at least {MIN_SCENES} clear dates required."
        )
    valid_final = inside & (counts >= 2)
    values = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    values[valid_final] = (summed[valid_final] / counts[valid_final]).astype("float32")
    if valid_final.sum() < 16 or valid_final.sum() / inside.sum() < 0.5:
        raise ValueError("Final season has insufficient multi-date pixel coverage.")
    pixels = [round(float(x), 4) if np.isfinite(x) else None for x in values.ravel()]
    mask = [bool(x) for x in inside.ravel()]
    return {
        "width": WIDTH, "height": HEIGHT, "projection": crs.to_string(),
        "transform": [round(float(v), 7) for v in tuple(aligned_transform)[:6]],
        "mask": mask, "pixels": pixels,
        "mean_ndvi": round(float(np.nanmean(values)), 4),
        "scene_count": len(used_dates), "scene_dates": used_dates,
        "failed_scene_attempts": failures,
        "quality": ">=80% clear field pixels per scene; >=2 readings per saved cell",
        "source": "sentinel-2-l2a", "method": "season_pixel_mean_v1",
    }

def claim():
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT id, field_id, start_date, end_date, boundary_hash
            FROM seasonal_zone_composites WHERE status='pending'
            ORDER BY requested_at, year FOR UPDATE SKIP LOCKED LIMIT 1
        """)).mappings().first()
        if row is None:
            return None
        conn.execute(text("""
            UPDATE seasonal_zone_composites SET status='running',
            started_at=now(), error=NULL WHERE id=:id
        """), {"id": row["id"]})
        return dict(row)

def run_job(job):
    with engine.connect() as conn:
        data = conn.execute(text("""
            SELECT ST_AsGeoJSON(boundary) AS boundary, ST_AsEWKB(boundary) AS binary
            FROM fields WHERE id=:field_id
        """), {"field_id":job["field_id"]}).mappings().first()
    if not data or hashlib.sha256(bytes(data["binary"])).hexdigest() != job["boundary_hash"]:
        raise ValueError("Field boundary changed or field was deleted; explicitly recalculate.")
    result = compute_season(json.loads(data["boundary"]),job["start_date"],job["end_date"])
    with engine.begin() as conn:
        latest = conn.execute(text(
            "SELECT ST_AsEWKB(boundary) FROM fields WHERE id=:field_id"
        ), {"field_id": job["field_id"]}).scalar_one_or_none()
        if latest is None or hashlib.sha256(bytes(latest)).hexdigest() != job["boundary_hash"]:
            raise ValueError("Field boundary changed during calculation.")
        conn.execute(text("""
            UPDATE seasonal_zone_composites
            SET status='completed', result_json=CAST(:payload AS jsonb),
            completed_at=now(), error=NULL WHERE id=:id AND status='running'
        """), {"id":job["id"],"payload":json.dumps(result)})
    LOG.info("Computed one final %s-season composite from %s dates",job["start_date"],result["scene_count"])

def run_once():
    job=claim()
    if job is None:
        return False
    try:
        run_job(job)
    except Exception as exc:
        LOG.exception("Historical season calculation failed")
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE seasonal_zone_composites SET status='failed',
                error=:error, completed_at=now(), result_json=NULL
                WHERE id=:id AND status='running'
            """), {"id": job["id"], "error": str(exc)[:800]})
    return True

def main():
    parser=argparse.ArgumentParser()
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.once:
        run_once()
    else:
        while True:
            if not run_once():
                time.sleep(15)

if __name__ == "__main__":
    main()
