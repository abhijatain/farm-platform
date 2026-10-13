
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.satellite_observation import SatelliteObservation


class SatelliteMetric(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Canonical store for every computed satellite metric.

    One observation can have NDVI, NDMI, NDRE, BSI, etc. Each metric owns
    its raster URI, summary statistics, coverage and processing metadata.
    """

    __tablename__ = "satellite_metrics"

    __table_args__ = (
        UniqueConstraint(
            "satellite_observation_id",
            "metric_type",
            name=(
                "uq_satellite_metrics_"
                "observation_metric"
            ),
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

    # Deliberately a string rather than a PostgreSQL enum so new metrics can
    # be introduced without a DB enum migration.
    metric_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    raster_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    mean: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    median: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    min: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    max: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    std: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    native_resolution_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    output_resolution_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    pixel_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    valid_pixel_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    valid_pixel_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Formula/calibration/storage/anomaly-analysis metadata belongs here
    # because those details are specific to this metric result.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    observation: Mapped["SatelliteObservation"] = relationship(
        back_populates="metrics",
    )
