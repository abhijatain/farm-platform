import json
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from satellite_worker.config import settings

engine = create_engine(
    settings.database_url,
)


def get_field_geometry(
    field_id: UUID,
) -> dict:

    query = text(
        """
        SELECT
            ST_AsGeoJSON(boundary)
            AS geometry
        FROM fields
        WHERE id = :field_id
        """
    )

    with engine.connect() as connection:

        row = (
            connection.execute(
                query,
                {
                    "field_id": field_id,
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise ValueError(f"Field not found: {field_id}")

    geometry = row["geometry"]

    if isinstance(
        geometry,
        str,
    ):
        geometry = json.loads(geometry)

    return geometry


def save_satellite_observation(
    *,
    field_id: UUID,
    observed_on: date,
    scene_id: str,
    cloud_cover_percent: float | None,
    valid_pixel_percent: float,
    ndvi_mean: float,
    ndvi_median: float,
    ndvi_min: float,
    ndvi_max: float,
    ndvi_std: float,
    ndvi_raster_uri: str,
    resolution_m: float,
    pixel_count: int,
    valid_pixel_count: int,
    metadata_json: dict,
) -> UUID:

    observation_id = uuid4()

    query = text(
        """
        INSERT INTO satellite_observations (
            id,
            field_id,

            observed_on,

            source,
            scene_id,

            cloud_cover_percent,
            valid_pixel_percent,

            ndvi_mean,
            ndvi_median,
            ndvi_min,
            ndvi_max,
            ndvi_std,

            ndwi_mean,

            ndvi_raster_uri,

            resolution_m,

            pixel_count,
            valid_pixel_count,

            metadata_json,

            created_at,
            updated_at
        )
        VALUES (
            :id,
            :field_id,

            :observed_on,

            'sentinel-2',
            :scene_id,

            :cloud_cover_percent,
            :valid_pixel_percent,

            :ndvi_mean,
            :ndvi_median,
            :ndvi_min,
            :ndvi_max,
            :ndvi_std,

            NULL,

            :ndvi_raster_uri,

            :resolution_m,

            :pixel_count,
            :valid_pixel_count,

            CAST(
                :metadata_json
                AS jsonb
            ),

            NOW(),
            NOW()
        )

        ON CONFLICT (
            field_id,
            scene_id
        )

        DO UPDATE SET

            observed_on =
                EXCLUDED.observed_on,

            cloud_cover_percent =
                EXCLUDED.cloud_cover_percent,

            valid_pixel_percent =
                EXCLUDED.valid_pixel_percent,

            ndvi_mean =
                EXCLUDED.ndvi_mean,

            ndvi_median =
                EXCLUDED.ndvi_median,

            ndvi_min =
                EXCLUDED.ndvi_min,

            ndvi_max =
                EXCLUDED.ndvi_max,

            ndvi_std =
                EXCLUDED.ndvi_std,

            ndvi_raster_uri =
                EXCLUDED.ndvi_raster_uri,

            resolution_m =
                EXCLUDED.resolution_m,

            pixel_count =
                EXCLUDED.pixel_count,

            valid_pixel_count =
                EXCLUDED.valid_pixel_count,

            metadata_json =
                EXCLUDED.metadata_json,

            updated_at =
                NOW()

        RETURNING id
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query,
            {
                "id": observation_id,
                "field_id": field_id,
                "observed_on": observed_on,
                "scene_id": scene_id,
                "cloud_cover_percent": cloud_cover_percent,
                "valid_pixel_percent": valid_pixel_percent,
                "ndvi_mean": ndvi_mean,
                "ndvi_median": ndvi_median,
                "ndvi_min": ndvi_min,
                "ndvi_max": ndvi_max,
                "ndvi_std": ndvi_std,
                "ndvi_raster_uri": ndvi_raster_uri,
                "resolution_m": resolution_m,
                "pixel_count": pixel_count,
                "valid_pixel_count": valid_pixel_count,
                "metadata_json": json.dumps(metadata_json),
            },
        )

        saved_id = result.scalar_one()

    return saved_id


def replace_satellite_anomalies(
    *,
    observation_id: UUID,
    field_id: UUID,
    zones: list,
    analysis_json: dict,
) -> None:

    delete_query = text(
        """
        DELETE FROM satellite_anomalies
        WHERE satellite_observation_id
            = :observation_id
        """
    )

    insert_query = text(
        """
        INSERT INTO satellite_anomalies (
            id,

            satellite_observation_id,
            field_id,

            zone_index,

            index_type,
            anomaly_type,

            severity,

            geometry,

            pixel_count,

            area_sqm,
            area_acres,

            zone_mean_value,
            zone_min_value,

            field_mean_value,
            field_median_value,

            threshold_value,

            difference_from_field,
            percent_difference,

            detection_method,

            metadata_json,

            created_at,
            updated_at
        )
        VALUES (
            :id,

            :observation_id,
            :field_id,

            :zone_index,

            'ndvi',
            'below_field_baseline',

            :severity,

            ST_Multi(
                ST_SetSRID(
                    ST_GeomFromGeoJSON(
                        :geometry_json
                    ),
                    4326
                )
            ),

            :pixel_count,

            :area_sqm,
            :area_acres,

            :zone_mean_value,
            :zone_min_value,

            :field_mean_value,
            :field_median_value,

            :threshold_value,

            :difference_from_field,
            :percent_difference,

            'robust_mad_v1',

            CAST(
                :metadata_json
                AS jsonb
            ),

            NOW(),
            NOW()
        )
        """
    )

    update_observation_query = text(
        """
        UPDATE satellite_observations

        SET
            metadata_json =
                jsonb_set(
                    COALESCE(
                        metadata_json,
                        '{}'::jsonb
                    ),

                    '{anomaly_detection}',

                    CAST(
                        :analysis_json
                        AS jsonb
                    ),

                    true
                ),

            updated_at =
                NOW()

        WHERE id =
            :observation_id
        """
    )

    with engine.begin() as connection:

        connection.execute(
            delete_query,
            {
                "observation_id": observation_id,
            },
        )

        for zone in zones:

            connection.execute(
                insert_query,
                {
                    "id": uuid4(),
                    "observation_id": observation_id,
                    "field_id": field_id,
                    "zone_index": zone.zone_index,
                    "severity": zone.severity,
                    "geometry_json": json.dumps(zone.geometry),
                    "pixel_count": zone.pixel_count,
                    "area_sqm": zone.area_sqm,
                    "area_acres": zone.area_acres,
                    "zone_mean_value": zone.zone_mean_value,
                    "zone_min_value": zone.zone_min_value,
                    "field_mean_value": zone.field_mean_value,
                    "field_median_value": zone.field_median_value,
                    "threshold_value": zone.threshold_value,
                    "difference_from_field": zone.difference_from_field,
                    "percent_difference": zone.percent_difference,
                    "metadata_json": json.dumps(zone.metadata_json),
                },
            )

        connection.execute(
            update_observation_query,
            {
                "observation_id": observation_id,
                "analysis_json": json.dumps(analysis_json),
            },
        )
