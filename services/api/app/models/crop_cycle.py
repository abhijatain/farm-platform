from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class CropCycle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crop_cycles"

    season_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "seasons.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    crop_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    variety: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True,
    )

    started_on: Mapped[date] = mapped_column(
        nullable=False,
    )

    planted_on: Mapped[date | None] = mapped_column(
        nullable=True,
    )

    expected_harvest_on: Mapped[date | None] = mapped_column(
        nullable=True,
    )

    harvested_on: Mapped[date | None] = mapped_column(
        nullable=True,
    )

    yield_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    harvested_area_acres: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    moisture_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    quality_grade: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    selling_price_per_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    harvest_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    season: Mapped["Season"] = relationship(
        back_populates="crop_cycles",
    )

    field: Mapped["Field"] = relationship(
        back_populates="crop_cycles",
    )

    stage_observations: Mapped[list["CropStageObservation"]] = relationship(
        back_populates="crop_cycle",
        cascade="all, delete-orphan",
        order_by="CropStageObservation.observed_on",
    )

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="crop_cycle",
        order_by="Activity.occurred_at",
    )
