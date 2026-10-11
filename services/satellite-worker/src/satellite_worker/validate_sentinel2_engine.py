from __future__ import annotations

import argparse
import json

import numpy as np

from pystac_client import Client
from sqlalchemy import create_engine, text

from satellite_worker.config import settings
from satellite_worker.sentinel2.grid import (
    build_analysis_grid,
    build_scene_valid_mask,
    read_scl,
    read_spectral_band,
)
from satellite_worker.sentinel2.reflectance import (
    print_reflectance_diagnostics,
    to_reflectance,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--field-id",
        required=True,
    )

    parser.add_argument(
        "--scene-id",
        required=True,
    )

    return parser.parse_args()


def get_database_reference(
    *,
    field_id: str,
    scene_id: str,
) -> tuple[
    dict,
    dict,
]:
    engine = create_engine(settings.database_url)

    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                SELECT
                    ST_AsGeoJSON(
                        f.boundary
                    ) AS boundary_geojson,

                    so.ndvi_mean,
                    so.ndvi_median,
                    so.ndvi_min,
                    so.ndvi_max,
                    so.ndvi_std,
                    so.valid_pixel_percent

                FROM fields f

                JOIN satellite_observations so
                    ON so.field_id = f.id

                WHERE
                    f.id = :field_id
                    AND so.scene_id = :scene_id

                LIMIT 1
                """
                ),
                {
                    "field_id": (field_id),
                    "scene_id": (scene_id),
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise RuntimeError(
            "Could not find the field/" "observation pair in the " "database."
        )

    geometry = json.loads(row["boundary_geojson"])

    reference = {
        "mean": (row["ndvi_mean"]),
        "median": (row["ndvi_median"]),
        "min": (row["ndvi_min"]),
        "max": (row["ndvi_max"]),
        "std": (row["ndvi_std"]),
        "valid_pixel_percent": (row["valid_pixel_percent"]),
    }

    return (
        geometry,
        reference,
    )


def get_scene(
    scene_id: str,
):
    catalog = Client.open(settings.earth_search_url)

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        ids=[scene_id],
    )

    items = list(search.items())

    if not items:
        raise RuntimeError(f"Scene not found: " f"{scene_id}")

    return items[0]


def calculate_stats(
    values: np.ndarray,
) -> dict:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "std": float(np.std(values)),
    }


def print_comparison(
    *,
    reference: dict,
    calculated: dict,
) -> float:
    print()
    print("NDVI comparison")

    print("----------------")

    biggest_difference = 0.0

    for key in [
        "mean",
        "median",
        "min",
        "max",
        "std",
    ]:
        database_value = reference.get(key)

        new_value = calculated[key]

        if database_value is None:
            print(f"{key:8} " f"database=None " f"new={new_value:.6f}")

            continue

        difference = abs(float(database_value) - new_value)

        biggest_difference = max(
            biggest_difference,
            difference,
        )

        print(
            f"{key:8} "
            f"database="
            f"{float(database_value):.6f} "
            f"new="
            f"{new_value:.6f} "
            f"delta="
            f"{difference:.8f}"
        )

    return biggest_difference


def main() -> None:
    args = parse_args()

    (
        field_geometry,
        reference,
    ) = get_database_reference(
        field_id=args.field_id,
        scene_id=args.scene_id,
    )

    item = get_scene(args.scene_id)

    print()
    print(
        "Scene:",
        item.id,
    )

    print(
        "Baseline:",
        item.properties.get("s2:" "processing_baseline"),
    )

    print(
        "BOA offset applied:",
        item.properties.get("earthsearch:" "boa_offset_applied"),
    )

    grid = build_analysis_grid(
        item=item,
        field_geometry=(field_geometry),
    )

    red = read_spectral_band(
        item=item,
        grid=grid,
        band_name="red",
    )

    nir = read_spectral_band(
        item=item,
        grid=grid,
        band_name="nir",
    )

    scl = read_scl(
        item=item,
        grid=grid,
    )

    base_valid = build_scene_valid_mask(
        grid=grid,
        scl=scl,
        bands=[
            red,
            nir,
        ],
    )

    denominator = nir.data + red.data

    valid = base_valid & (red.data > 0) & (nir.data > 0) & (np.abs(denominator) > 1e-6)

    candidate_ndvi = np.full(
        (
            grid.height,
            grid.width,
        ),
        np.nan,
        dtype=np.float32,
    )

    candidate_ndvi[valid] = (nir.data[valid] - red.data[valid]) / denominator[valid]

    physical = (
        np.isfinite(candidate_ndvi) & (candidate_ndvi >= -1.0) & (candidate_ndvi <= 1.0)
    )

    final_valid = valid & physical

    ndvi_values = candidate_ndvi[final_valid]

    if ndvi_values.size == 0:
        raise RuntimeError("No valid NDVI pixels.")

    calculated = calculate_stats(ndvi_values)

    valid_pixel_count = int(final_valid.sum())

    valid_pixel_percent = valid_pixel_count / grid.pixel_count * 100.0

    print()
    print("Generic engine grid")

    print("-------------------")

    print(
        "Resolution:",
        grid.resolution_m,
        "m",
    )

    print(
        "Field pixels:",
        grid.pixel_count,
    )

    print(
        "Valid pixels:",
        valid_pixel_count,
    )

    print(
        "Valid coverage:",
        f"{valid_pixel_percent:.2f}%",
    )

    biggest_difference = print_comparison(
        reference=reference,
        calculated=calculated,
    )

    red_reflectance, red_cal = to_reflectance(
        item=item,
        asset=red.asset,
        data=red.data,
    )

    nir_reflectance, nir_cal = to_reflectance(
        item=item,
        asset=nir.asset,
        data=nir.data,
    )

    print_reflectance_diagnostics(
        name="RED",
        values=red_reflectance,
        valid_mask=final_valid,
        calibration=red_cal,
    )

    print_reflectance_diagnostics(
        name="NIR",
        values=nir_reflectance,
        valid_mask=final_valid,
        calibration=nir_cal,
    )

    reflectance_denominator = nir_reflectance + red_reflectance

    reflectance_valid = (
        final_valid
        & np.isfinite(reflectance_denominator)
        & (np.abs(reflectance_denominator) > 1e-8)
    )

    reflectance_ndvi = (
        nir_reflectance[reflectance_valid] - red_reflectance[reflectance_valid]
    ) / reflectance_denominator[reflectance_valid]

    reflectance_stats = calculate_stats(reflectance_ndvi)

    print()
    print("Reflectance NDVI")

    print("----------------")

    for key, value in reflectance_stats.items():
        print(f"{key:8} " f"{value:.6f}")

    print()
    print(
        "Largest difference from " "current NDVI pipeline:",
        f"{biggest_difference:.8f}",
    )

    print()

    if biggest_difference <= 0.0001:
        print("PASS: generic engine " "matches current NDVI.")

    else:
        print("FAIL: do not migrate " "NDVI to the generic " "engine yet.")


if __name__ == "__main__":
    main()
