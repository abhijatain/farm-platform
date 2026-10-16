"""On-demand season raster averages; no raw historical scenes are persisted."""
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

class SeasonalZoneComposite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seasonal_zone_composites"
    __table_args__ = (
        UniqueConstraint("field_id", "crop_key", "calendar_key", "year", name="uq_seasonal_zone_field_crop_calendar_year"),
        Index("ix_seasonal_composites_pending", "status", "requested_at"),
    )
    field_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), index=True, nullable=False)
    crop_key: Mapped[str] = mapped_column(String(100), nullable=False)
    calendar_key: Mapped[str] = mapped_column(String(32), nullable=False)
    season_label: Mapped[str] = mapped_column(String(120), nullable=False)
    window_source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="reference_calendar")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    boundary_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    # Only small final aligned seasonal NDVI means/counts, and zones. No raw scenes.
    result_json: Mapped[dict | None] = mapped_column(JSONB)
