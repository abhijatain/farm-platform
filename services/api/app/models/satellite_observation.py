
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.field import Field
    from app.models.satellite_metric import SatelliteMetric


class SatelliteObservation(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    One source scene observed for one field.

    Metric values, coverage, resolutions, pixel counts and raster URIs do
    not belong here. They live only in satellite_metrics.
    """

    __tablename__ = "satellite_observations"

    __table_args__ = (
        UniqueConstraint(
            "field_id",
            "scene_id",
            name=(
                "uq_satellite_observation_"
                "field_scene"
            ),
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

    # Scene-level STAC cloud-cover estimate. This is intentionally separate
    # from per-field/per-metric valid pixel coverage.
    cloud_cover_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Scene/source metadata only: STAC collection, platform, acquisition
    # datetime, processing baseline, etc.
    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    field: Mapped["Field"] = relationship(
        back_populates="satellite_observations",
    )

    metrics: Mapped[list["SatelliteMetric"]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SatelliteMetric.metric_type",
    )
