"""One farmer-owned WhatsApp identity and consent record per Firebase user.

Pending codes are SHA-256 hashes, never cleartext. Unlinked and revoked
records are retained for audit without leaving an active WhatsApp identity.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class WhatsAppLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_links"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    wa_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True,
    )
    phone_number_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    code_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True,
    )
    code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    preferred_language: Mapped[str] = mapped_column(
        String(2), nullable=False, default="en", server_default="en",
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
