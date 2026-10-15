"""Farmer-confirmed crop stage transitions.

Revision ID: c92531dd067f
Revises: d2b63f18a2c7
"""
from alembic import op
import sqlalchemy as sa

revision = "c92531dd067f"
down_revision = "d2b63f18a2c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crop_stage_observations",
        sa.Column("crop_cycle_id", sa.UUID(), nullable=False),
        sa.Column("stage_code", sa.String(length=40), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["crop_cycle_id"], ["crop_cycles.id"],
            name=op.f("fk_crop_stage_observations_crop_cycle_id_crop_cycles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crop_stage_observations")),
        sa.UniqueConstraint("crop_cycle_id", "stage_code", name="uq_crop_stage_observations_crop_stage"),
    )
    op.create_index(op.f("ix_crop_stage_observations_crop_cycle_id"), "crop_stage_observations", ["crop_cycle_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_crop_stage_observations_crop_cycle_id"), table_name="crop_stage_observations")
    op.drop_table("crop_stage_observations")
