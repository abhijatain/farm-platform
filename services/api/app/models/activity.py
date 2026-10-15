"""Persist field operations with timestamps and input details."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Activity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "activities"

    field_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "fields.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    crop_cycle_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "crop_cycles.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    activity_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    field: Mapped["Field"] = relationship(
        back_populates="activities",
    )

    crop_cycle: Mapped["CropCycle | None"] = relationship(
        back_populates="activities",
    )
