"""Produce single-use replies and safely dispatch an outbound queue.

The webhook only inserts inbound records. A separate worker claims each row,
applies deterministic conversation rules and sends via Meta only when enabled.
Sending rows aren't automatically retried after a crash because Meta may have
accepted the message before the process lost its database connection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.whatsapp.conversation import interpret
from app.domains.whatsapp.outbound import WhatsAppSendError, send_text
from app.models.whatsapp import WhatsAppContact, WhatsAppInbound, WhatsAppOutbound


SERVICE_WINDOW = timedelta(hours=23)  # Safety margin under Meta's 24h window.


def _fresh(sent_at: datetime, now: datetime) -> bool:
    """Only reply to recent farmer-initiated messages, never broadcast."""
    return timedelta(0) <= now - sent_at < SERVICE_WINDOW


def process_one(db: Session, *, now: datetime | None = None) -> bool:
    """Claim an inbound event and transactionally create at most one reply."""
    current = now or datetime.now(timezone.utc)
    row = db.scalar(
        select(WhatsAppInbound)
        .where(WhatsAppInbound.state == "pending")
        .order_by(WhatsAppInbound.created_at, WhatsAppInbound.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        db.rollback()
        return False
    contact = db.scalar(
        select(WhatsAppContact)
        .where(WhatsAppContact.id == row.contact_id)
        .with_for_update()
    )
    if contact is None:
        row.state = "processed"
        db.commit()
        return True
    # Old queued messages cannot reopen a Meta customer-service window.
    if _fresh(row.sent_at, current):
        language, updates_opt_in, reply = interpret(
            row.command, contact.language, contact.updates_opt_in,
        )
        contact.language = language
        contact.updates_opt_in = updates_opt_in
        db.add(WhatsAppOutbound(
            contact_id=contact.id,
            inbound_id=row.id,
            body=reply,
            state="pending",
        ))
    elif row.command == "STOP":
        # Honor delayed opt-outs without sending a non-template message.
        contact.updates_opt_in = False
    row.state = "processed"
    db.commit()
    return True


def send_one(db: Session, *, now: datetime | None = None) -> bool:
    """Send one queued reply with an explicit no-auto-retry failure policy."""
    if not settings.whatsapp_sending_enabled:
        return False
    if not settings.whatsapp_access_token or not settings.whatsapp_access_token.get_secret_value():
        raise WhatsAppSendError("Sender is enabled but no access token is configured.")
    current = now or datetime.now(timezone.utc)
    row = db.scalar(
        select(WhatsAppOutbound)
        .where(WhatsAppOutbound.state == "pending")
        .order_by(WhatsAppOutbound.created_at, WhatsAppOutbound.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        db.rollback()
        return False
    event = db.get(WhatsAppInbound, row.inbound_id)
    contact = db.get(WhatsAppContact, row.contact_id)
    if event is None or contact is None or not _fresh(event.sent_at, current):
        row.state = "skipped"
        row.failure_reason = "service_window_closed"
        db.commit()
        return True
    if contact.phone_number_id != settings.whatsapp_phone_number_id:
        row.state = "skipped"
        row.failure_reason = "phone_number_changed"
        db.commit()
        return True

    # Commit 'sending' before network I/O. A crash leaves it for human review
    # rather than sending a duplicate message on the next worker run.
    row.state = "sending"
    row.attempted_at = current
    db.commit()
    try:
        provider_id = send_text(recipient=contact.wa_id, body=row.body)
    except WhatsAppSendError:
        row.state = "failed"
        row.failure_reason = "provider_failure"
    else:
        row.state = "accepted"
        row.provider_message_id = provider_id
    db.commit()
    return True


def drain_once(db: Session, *, limit: int = 100) -> tuple[int, int]:
    """Process bounded events; only send if explicitly enabled by operator."""
    processed = 0
    for _ in range(limit):
        if not process_one(db):
            break
        processed += 1
    sent = 0
    if settings.whatsapp_sending_enabled:
        for _ in range(limit):
            if not send_one(db):
                break
            sent += 1
    return processed, sent
