from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SatelliteIngestionJob(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "satellite_ingestion_jobs"

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('initial_backfill', 'incremental')",
            name="satellite_ingestion_job_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="satellite_ingestion_job_status",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="satellite_ingestion_attempts_nonnegative",
        ),
        CheckConstraint(
            "max_attempts >= 1",
            name="satellite_ingestion_max_attempts_positive",
        ),
        CheckConstraint(
            "start_date <= end_date",
            name="satellite_ingestion_date_range",
        ),
        Index(
            "ix_satellite_ingestion_jobs_claim",
            "status",
            "available_at",
            "created_at",
        ),
        Index(
            "uq_satellite_ingestion_jobs_running_field",
            "field_id",
            unique=True,
            postgresql_where=text(
                "status = 'running'"
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

    job_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    dedupe_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
