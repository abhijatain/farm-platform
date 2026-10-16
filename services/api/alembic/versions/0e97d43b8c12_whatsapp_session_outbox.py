"""Add durable WhatsApp session reply outbox.

Revision ID: 0e97d43b8c12
Revises: 69d301c9a4fb
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0e97d43b8c12"
down_revision = "69d301c9a4fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("inbound_message_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("recipient_wa_id", sa.String(32), nullable=False),
        sa.Column("phone_number_id", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reply_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta_message_id", sa.String(255), nullable=True),
        sa.Column("last_error", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_whatsapp_outbox_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_outbox")),
        sa.UniqueConstraint("inbound_message_id", name=op.f("uq_whatsapp_outbox_inbound_message_id")),
    )
    op.create_index(op.f("ix_whatsapp_outbox_meta_message_id"), "whatsapp_outbox", ["meta_message_id"], unique=False)
    op.create_index(
        "ix_whatsapp_outbox_ready", "whatsapp_outbox",
        ["status", "available_at", "created_at"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_outbox_ready", table_name="whatsapp_outbox")
    op.drop_index(op.f("ix_whatsapp_outbox_meta_message_id"), table_name="whatsapp_outbox")
    op.drop_table("whatsapp_outbox")
