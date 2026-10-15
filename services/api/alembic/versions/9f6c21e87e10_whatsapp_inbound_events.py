"""Add a minimal idempotent WhatsApp webhook inbox.

Revision ID: 9f6c21e87e10
Revises: c92531dd067f
"""
from alembic import op
import sqlalchemy as sa

revision = "9f6c21e87e10"
down_revision = "c92531dd067f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_inbound_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("sender_wa_id", sa.String(length=32), nullable=False),
        sa.Column("phone_number_id", sa.String(length=40), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_inbound_events")),
        sa.UniqueConstraint("message_id", name=op.f("uq_whatsapp_inbound_events_message_id")),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_inbound_events")
