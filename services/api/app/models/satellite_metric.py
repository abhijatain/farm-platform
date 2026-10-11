from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.satellite_observation import SatelliteObservation


class SatelliteMetric(Base):
    __tablename__ = "satellite_metrics"

    __table_args__ = (
        UniqueConstraint(
            "satellite_observation_id",
            "metric_type",
            name="uq_satellite_metrics_observation_metric",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    satellite_observation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "satellite_observations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Examples:
    #
    # ndvi
    # ndre
    # ndmi
    # gndvi
    # evi2
    # ndwi
    # savi
    # msavi
    # bsi
    # ndti
    # ccci
    # reci
    # mcari
    metric_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    # We deliberately use a string rather than a
    # PostgreSQL enum because more metrics can be
    # introduced later without a DB enum migration.

    raster_uri: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    # Example:
    #
    # NDVI:
    # native_resolution_m = 10
    # output_resolution_m = 10
    #
    # NDRE:
    # native_resolution_m = 20
    # output_resolution_m could later be 10
    # if resampled to the common analysis grid.
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

    # Useful later for things such as:
    #
    # {
    #     "formula": "ndvi_v1",
    #     "bands": ["red", "nir"],
    #     "native_resolution_m": 10,
    #     "resampling": null,
    #     "reflectance_method": "...",
    # }
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    observation: Mapped["SatelliteObservation"] = relationship(
        back_populates="metrics",
    )
