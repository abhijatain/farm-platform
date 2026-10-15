"""Persist minimal WhatsApp contact preferences and idempotent message state.

These records are *not* farm authorization. A WhatsApp sender may only access
farm records after a separate, explicit Firebase account-linking flow.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class WhatsAppContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_contacts"
    __table_args__ = (
        UniqueConstraint("phone_number_id", "wa_id", name="uq_whatsapp_contacts_phone_wa"),
    )

    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False)
    wa_id: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="und", server_default="und")
    updates_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WhatsAppInbound(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_inbound"
    __table_args__ = (
        UniqueConstraint("phone_number_id", "external_id", name="uq_whatsapp_inbound_phone_external"),
        Index("ix_whatsapp_inbound_state_created", "state", "created_at"),
    )

    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Only store a closed-set command; raw farmer conversations are not retained.
    command: Mapped[str] = mapped_column(String(32), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")


class WhatsAppOutbound(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_outbound"
    __table_args__ = (
        UniqueConstraint("inbound_id", name="uq_whatsapp_outbound_inbound"),
        Index("ix_whatsapp_outbound_state_created", "state", "created_at"),
    )

    contact_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    inbound_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("whatsapp_inbound.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    # 'sending' is intentionally not automatically retried: a crash after Meta
    # accepts a message could otherwise send the same message twice.
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
