"""Durable, idempotent metadata-only inbox for verified Meta messages.

Message bodies and precise locations are intentionally not persisted.
Conversation dispatch and media processing will be a later, consent-gated PR.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import UUIDPrimaryKeyMixin


class WhatsAppInboundEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "whatsapp_inbound_events"

    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sender_wa_id: Mapped[str] = mapped_column(String(32), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String(40), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
