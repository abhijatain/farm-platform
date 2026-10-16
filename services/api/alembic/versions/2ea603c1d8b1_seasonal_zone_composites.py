"""On-demand compact seasonal NDVI composites.

Revision ID: 2ea603c1d8b1
Revises: 69d301c9a4fb
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "2ea603c1d8b1"
down_revision = "69d301c9a4fb"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "seasonal_zone_composites",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("field_id", sa.UUID(), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crop_key", sa.String(100), nullable=False),
        sa.Column("calendar_key", sa.String(32), nullable=False),
        sa.Column("season_label", sa.String(120), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("boundary_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("result_json", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("field_id","crop_key","calendar_key","year",name="uq_seasonal_zone_field_crop_calendar_year"),
    )
    op.create_index("ix_seasonal_zone_composites_field_id", "seasonal_zone_composites", ["field_id"])
    op.create_index("ix_seasonal_composites_pending", "seasonal_zone_composites", ["status","requested_at"])

def downgrade():
    op.drop_index("ix_seasonal_composites_pending", table_name="seasonal_zone_composites")
    op.drop_index("ix_seasonal_zone_composites_field_id", table_name="seasonal_zone_composites")
    op.drop_table("seasonal_zone_composites")
