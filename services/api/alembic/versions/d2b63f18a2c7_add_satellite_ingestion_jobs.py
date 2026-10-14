"""add satellite ingestion jobs

Revision ID: d2b63f18a2c7
Revises: a693eb822c3c
Create Date: 2026-10-14 19:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d2b63f18a2c7"
down_revision: Union[str, Sequence[str], None] = "a693eb822c3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "satellite_ingestion_jobs",
        sa.Column(
            "field_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "job_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "start_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "end_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "dedupe_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_satellite_ingestion_jobs_satellite_ingestion_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "job_type IN ('initial_backfill', 'incremental')",
            name="ck_satellite_ingestion_jobs_satellite_ingestion_job_type",
        ),
        sa.CheckConstraint(
            "max_attempts >= 1",
            name="ck_satellite_ingestion_jobs_satellite_ingestion_max_attempts_positive",
        ),
        sa.CheckConstraint(
            "start_date <= end_date",
            name="ck_satellite_ingestion_jobs_satellite_ingestion_date_range",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_satellite_ingestion_jobs_satellite_ingestion_job_status",
        ),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["fields.id"],
            name=op.f(
                "fk_satellite_ingestion_jobs_field_id_fields"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f(
                "pk_satellite_ingestion_jobs"
            ),
        ),
        sa.UniqueConstraint(
            "dedupe_key",
            name=op.f(
                "uq_satellite_ingestion_jobs_dedupe_key"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_satellite_ingestion_jobs_available_at"
        ),
        "satellite_ingestion_jobs",
        ["available_at"],
        unique=False,
    )

    op.create_index(
        "ix_satellite_ingestion_jobs_claim",
        "satellite_ingestion_jobs",
        [
            "status",
            "available_at",
            "created_at",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_satellite_ingestion_jobs_field_id"
        ),
        "satellite_ingestion_jobs",
        ["field_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_satellite_ingestion_jobs_status"
        ),
        "satellite_ingestion_jobs",
        ["status"],
        unique=False,
    )

    op.create_index(
        "uq_satellite_ingestion_jobs_running_field",
        "satellite_ingestion_jobs",
        ["field_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'running'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_satellite_ingestion_jobs_running_field",
        table_name="satellite_ingestion_jobs",
        postgresql_where=sa.text(
            "status = 'running'"
        ),
    )

    op.drop_index(
        op.f(
            "ix_satellite_ingestion_jobs_status"
        ),
        table_name="satellite_ingestion_jobs",
    )

    op.drop_index(
        op.f(
            "ix_satellite_ingestion_jobs_field_id"
        ),
        table_name="satellite_ingestion_jobs",
    )

    op.drop_index(
        "ix_satellite_ingestion_jobs_claim",
        table_name="satellite_ingestion_jobs",
    )

    op.drop_index(
        op.f(
            "ix_satellite_ingestion_jobs_available_at"
        ),
        table_name="satellite_ingestion_jobs",
    )

    op.drop_table(
        "satellite_ingestion_jobs"
    )
