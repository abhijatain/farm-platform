from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Season(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seasons"

    farm_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "farms.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    season_type: Mapped[str | None] = mapped_column(
        String(30),
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

    ended_on: Mapped[date | None] = mapped_column(
        nullable=True,
    )

    farm: Mapped["Farm"] = relationship(
        back_populates="seasons",
    )

    crop_cycles: Mapped[list["CropCycle"]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
    )
