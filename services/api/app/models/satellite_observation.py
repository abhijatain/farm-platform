from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SatelliteObservation(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "satellite_observations"

    __table_args__ = (
        UniqueConstraint(
            "field_id",
            "scene_id",
            name=("uq_satellite_observation_" "field_scene"),
        ),
    )

    field_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "fields.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    observed_on: Mapped[date] = mapped_column(
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="sentinel-2",
    )

    scene_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    cloud_cover_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    valid_pixel_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ndvi_mean: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ndvi_min: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ndvi_max: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ndvi_std: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ndwi_mean: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    ndvi_median: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ndvi_raster_uri: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    resolution_m: Mapped[float | None] = mapped_column(
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

    field: Mapped["Field"] = relationship(
        back_populates="satellite_observations",
    )
