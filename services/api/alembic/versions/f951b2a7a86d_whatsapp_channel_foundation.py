"""Create isolated WhatsApp contact, inbound deduplication and reply outbox.

Revision ID: f951b2a7a86d
Revises: c92531dd067f
"""

from alembic import op
import sqlalchemy as sa

revision = "f951b2a7a86d"
down_revision = "c92531dd067f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_contacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("phone_number_id", sa.String(64), nullable=False),
        sa.Column("wa_id", sa.String(128), nullable=False),
        sa.Column("language", sa.String(8), server_default="und", nullable=False),
        sa.Column("updates_opt_in", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_contacts")),
        sa.UniqueConstraint("phone_number_id", "wa_id", name="uq_whatsapp_contacts_phone_wa"),
    )
    op.create_table(
        "whatsapp_inbound",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("phone_number_id", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("command", sa.String(32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["whatsapp_contacts.id"],
            name=op.f("fk_whatsapp_inbound_contact_id_whatsapp_contacts"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_inbound")),
        sa.UniqueConstraint("phone_number_id", "external_id", name="uq_whatsapp_inbound_phone_external"),
    )
    op.create_index("ix_whatsapp_inbound_state_created", "whatsapp_inbound", ["state", "created_at"])
    op.create_table(
        "whatsapp_outbound",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("inbound_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("state", sa.String(16), server_default="pending", nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["whatsapp_contacts.id"],
            name=op.f("fk_whatsapp_outbound_contact_id_whatsapp_contacts"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inbound_id"], ["whatsapp_inbound.id"],
            name=op.f("fk_whatsapp_outbound_inbound_id_whatsapp_inbound"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_outbound")),
        sa.UniqueConstraint("inbound_id", name="uq_whatsapp_outbound_inbound"),
    )
    op.create_index("ix_whatsapp_outbound_state_created", "whatsapp_outbound", ["state", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_outbound_state_created", table_name="whatsapp_outbound")
    op.drop_table("whatsapp_outbound")
    op.drop_index("ix_whatsapp_inbound_state_created", table_name="whatsapp_inbound")
    op.drop_table("whatsapp_inbound")
    op.drop_table("whatsapp_contacts")
