from __future__ import annotations

import json

from pathlib import Path
from urllib.parse import (
    unquote,
    urlparse,
)

from sqlalchemy import text

from satellite_worker.anomaly import (
    detect_ndvi_anomalies,
)

from satellite_worker.db import (
    engine,
    replace_satellite_anomalies,
)


def file_uri_to_path(
    uri: str,
) -> Path:

    parsed = urlparse(uri)

    if parsed.scheme != "file":
        raise ValueError("Backfill currently supports " "file:// raster URIs only.")

    return Path(unquote(parsed.path))


def main() -> None:

    query = text(
        """
        SELECT
            so.id
                AS observation_id,

            so.field_id,

            so.observed_on,

            so.scene_id,

            so.ndvi_raster_uri,

            so.valid_pixel_percent,

            f.name
                AS field_name,

            ST_AsGeoJSON(
                f.boundary
            )
                AS field_geometry

        FROM satellite_observations so

        JOIN fields f
            ON f.id = so.field_id

        WHERE
            so.ndvi_raster_uri
                IS NOT NULL

        ORDER BY
            f.name,
            so.observed_on
        """
    )

    with engine.connect() as connection:

        rows = connection.execute(query).mappings().all()

    print(f"Found {len(rows)} " "processed raster observations.")

    for index, row in enumerate(
        rows,
        start=1,
    ):

        print()
        print("========================================")

        print(f"[{index}/{len(rows)}]")

        print(f"Field: " f"{row['field_name']}")

        print(f"Date: " f"{row['observed_on']}")

        print(f"Scene: " f"{row['scene_id']}")

        valid_percent = row["valid_pixel_percent"]

        if valid_percent is not None and valid_percent < 80.0:

            print("Skipped: " f"{valid_percent:.1f}% " "valid coverage.")

            replace_satellite_anomalies(
                observation_id=row["observation_id"],
                field_id=row["field_id"],
                zones=[],
                analysis_json={
                    "status": "skipped_low_valid_coverage",
                    "method": "robust_mad_v1",
                    "valid_pixel_percent": valid_percent,
                    "minimum_required_percent": 80.0,
                    "zone_count": 0,
                },
            )

            continue

        raster_path = file_uri_to_path(row["ndvi_raster_uri"])

        if not raster_path.exists():

            print("Raster missing: " f"{raster_path}")

            continue

        field_geometry = row["field_geometry"]

        if isinstance(
            field_geometry,
            str,
        ):
            field_geometry = json.loads(field_geometry)

        try:

            result = detect_ndvi_anomalies(
                raster_path=raster_path,
                field_geometry=field_geometry,
            )

            replace_satellite_anomalies(
                observation_id=row["observation_id"],
                field_id=row["field_id"],
                zones=result.zones,
                analysis_json=result.analysis,
            )

            print("Field median NDVI: " f"{result.analysis.get('field_median', 0):.3f}")

            print("Threshold: " f"{result.analysis.get('threshold', 0):.3f}")

            print(
                "Candidate pixels: "
                f"{result.analysis.get('candidate_pixel_count', 0)}"
            )

            print("Zones: " f"{len(result.zones)}")

            for zone in result.zones:

                difference = zone.percent_difference

                percent_text = f"{difference:.1f}%" if difference is not None else "n/a"

                print(
                    "  "
                    f"Zone {zone.zone_index}: "
                    f"{zone.severity}, "
                    f"{zone.area_acres:.3f} acre, "
                    f"mean={zone.zone_mean_value:.3f}, "
                    f"difference={percent_text}"
                )

        except Exception as error:

            print("FAILED: " f"{type(error).__name__}: " f"{error}")


if __name__ == "__main__":
    main()
