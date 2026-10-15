"""Add owner-scoped, consent-aware WhatsApp account links.

Revision ID: 69d301c9a4fb
Revises: 9f6c21e87e10
"""

from alembic import op
import sqlalchemy as sa

revision = "69d301c9a4fb"
down_revision = "9f6c21e87e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("wa_id", sa.String(length=32), nullable=True),
        sa.Column("phone_number_id", sa.String(length=40), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferred_language", sa.String(length=2), server_default="en", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_whatsapp_links_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_links")),
        sa.UniqueConstraint("wa_id", name=op.f("uq_whatsapp_links_wa_id")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_whatsapp_links_code_hash")),
    )
    op.create_index(op.f("ix_whatsapp_links_user_id"), "whatsapp_links", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_whatsapp_links_user_id"), table_name="whatsapp_links")
    op.drop_table("whatsapp_links")
