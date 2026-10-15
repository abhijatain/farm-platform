"""Farmer-verified crop phenology transitions, separate from predictions."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class CropStageObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crop_stage_observations"
    __table_args__ = (
        UniqueConstraint("crop_cycle_id", "stage_code", name="uq_crop_stage_observations_crop_stage"),
    )

    crop_cycle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("crop_cycles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    stage_code: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    crop_cycle: Mapped["CropCycle"] = relationship(back_populates="stage_observations")
