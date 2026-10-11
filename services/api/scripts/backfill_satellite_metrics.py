from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation


def main() -> None:
    db = SessionLocal()

    try:
        observations = db.scalars(
            select(SatelliteObservation).where(
                SatelliteObservation.ndvi_raster_uri.is_not(None)
            )
        ).all()

        created = 0
        skipped = 0

        for observation in observations:
            existing = db.scalar(
                select(SatelliteMetric).where(
                    SatelliteMetric.satellite_observation_id == observation.id,
                    SatelliteMetric.metric_type == "ndvi",
                )
            )

            if existing is not None:
                skipped += 1
                continue

            metric = SatelliteMetric(
                satellite_observation_id=observation.id,
                metric_type="ndvi",
                raster_uri=observation.ndvi_raster_uri,
                mean=observation.ndvi_mean,
                median=observation.ndvi_median,
                min=observation.ndvi_min,
                max=observation.ndvi_max,
                std=observation.ndvi_std,
                native_resolution_m=observation.resolution_m,
                output_resolution_m=observation.resolution_m,
                pixel_count=observation.pixel_count,
                valid_pixel_count=(observation.valid_pixel_count),
                valid_pixel_percent=(observation.valid_pixel_percent),
                metadata_json={
                    "formula": "ndvi_v1",
                    "calculation": ("direct_normalized_difference"),
                    "bands": [
                        "red",
                        "nir",
                    ],
                    "migrated_from": ("satellite_observations"),
                },
            )

            db.add(metric)

            created += 1

        db.commit()

        print()
        print("NDVI metric backfill complete.")

        print(f"Created: {created}")

        print(f"Skipped: {skipped}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
