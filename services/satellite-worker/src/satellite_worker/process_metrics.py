from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from uuid import uuid4

from pystac_client import Client
from sqlalchemy import create_engine, text

from satellite_worker.config import settings
from satellite_worker.sentinel2.processor import (
    process_metrics,
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


def main() -> None:
    args = parse_args()

    engine = create_engine(settings.database_url)

    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                SELECT
                    so.id AS observation_id,
                    so.observed_on,

                    ST_AsGeoJSON(
                        f.boundary
                    ) AS boundary_geojson

                FROM satellite_observations so

                JOIN fields f
                    ON f.id = so.field_id

                WHERE
                    so.field_id = :field_id
                    AND so.scene_id = :scene_id

                LIMIT 1
                """
                ),
                {
                    "field_id": (args.field_id),
                    "scene_id": (args.scene_id),
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise RuntimeError("Satellite observation " "does not exist in database.")

    field_geometry = json.loads(row["boundary_geojson"])

    observation_id = row["observation_id"]

    observed_on: date = row["observed_on"]

    catalog = Client.open(settings.earth_search_url)

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        ids=[args.scene_id],
    )

    items = list(search.items())

    if not items:
        raise RuntimeError(f"Scene not found: " f"{args.scene_id}")

    item = items[0]

    output_directory = (
        Path(settings.satellite_output_dir) / args.field_id / observed_on.isoformat()
    )

    results = process_metrics(
        item=item,
        field_geometry=(field_geometry),
        output_directory=(output_directory),
    )

    with engine.begin() as connection:
        for result in results:
            metadata = {
                "formula": (result.formula_version),
                "calibration_methods": (result.calibration_methods),
                "source": ("earth-search-" "sentinel-2-l2a"),
            }

            connection.execute(
                text(
                    """
                    INSERT INTO
                        satellite_metrics
                    (
                        id,
                        satellite_observation_id,
                        metric_type,
                        raster_uri,
                        mean,
                        median,
                        min,
                        max,
                        std,
                        native_resolution_m,
                        output_resolution_m,
                        pixel_count,
                        valid_pixel_count,
                        valid_pixel_percent,
                        metadata_json,
                        created_at,
                        updated_at
                    )

                    VALUES
                    (
                        :id,
                        :observation_id,
                        :metric_type,
                        :raster_uri,
                        :mean,
                        :median,
                        :minimum,
                        :maximum,
                        :std,
                        :native_resolution_m,
                        :output_resolution_m,
                        :pixel_count,
                        :valid_pixel_count,
                        :valid_pixel_percent,
                        CAST(
                            :metadata_json
                            AS jsonb
                        ),
                        now(),
                        now()
                    )

                    ON CONFLICT
                    (
                        satellite_observation_id,
                        metric_type
                    )

                    DO UPDATE SET
                        raster_uri =
                            EXCLUDED.raster_uri,

                        mean =
                            EXCLUDED.mean,

                        median =
                            EXCLUDED.median,

                        min =
                            EXCLUDED.min,

                        max =
                            EXCLUDED.max,

                        std =
                            EXCLUDED.std,

                        native_resolution_m =
                            EXCLUDED.native_resolution_m,

                        output_resolution_m =
                            EXCLUDED.output_resolution_m,

                        pixel_count =
                            EXCLUDED.pixel_count,

                        valid_pixel_count =
                            EXCLUDED.valid_pixel_count,

                        valid_pixel_percent =
                            EXCLUDED.valid_pixel_percent,

                        metadata_json =
                            EXCLUDED.metadata_json,

                        updated_at =
                            now()
                    """
                ),
                {
                    "id": str(uuid4()),
                    "observation_id": str(observation_id),
                    "metric_type": (result.metric_type),
                    "raster_uri": ("file://" + str(result.raster_path.resolve())),
                    "mean": (result.mean),
                    "median": (result.median),
                    "minimum": (result.minimum),
                    "maximum": (result.maximum),
                    "std": (result.std),
                    "native_resolution_m": (result.native_resolution_m),
                    "output_resolution_m": (result.output_resolution_m),
                    "pixel_count": (result.pixel_count),
                    "valid_pixel_count": (result.valid_pixel_count),
                    "valid_pixel_percent": (result.valid_pixel_percent),
                    "metadata_json": (json.dumps(metadata)),
                },
            )

    print()
    print(
        "Saved",
        len(results),
        "satellite metrics.",
    )


if __name__ == "__main__":
    main()
