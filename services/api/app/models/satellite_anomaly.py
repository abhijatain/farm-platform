"""Persist spatially delineated field-relative anomaly zones."""

from __future__ import annotations

from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SatelliteAnomaly(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "satellite_anomalies"

    __table_args__ = (
        UniqueConstraint(
            "satellite_observation_id",
            "index_type",
            "zone_index",
            name=(
                "uq_satellite_anomalies_"
                "observation_metric_zone"
            ),
        ),
        Index(
            "ix_satellite_anomalies_observation_metric",
            "satellite_observation_id",
            "index_type",
        ),
    )

    satellite_observation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "satellite_observations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Kept as index_type for now to avoid a needless rename migration. It
    # refers to the same logical value as satellite_metrics.metric_type.
    index_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ndvi",
    )

    zone_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    anomaly_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="below_field_baseline",
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    geometry: Mapped[WKBElement] = mapped_column(
        Geometry(
            geometry_type="MULTIPOLYGON",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )

    pixel_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    area_sqm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Materialized report/UI value. Although derivable from area_sqm, this
    # is retained intentionally because it is part of the saved analysis
    # result and heavily used by farmer-facing comparisons.
    area_acres: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    zone_mean_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    zone_min_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    zone_max_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    field_mean_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    field_median_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    threshold_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    difference_from_field: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    percent_difference: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    detection_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="robust_mad_metric_v1",
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
