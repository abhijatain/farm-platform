"""Transactional inbound-to-outbox handoff for authorized WhatsApp menus.

Webhook commits response intent before acknowledging Meta. Sender/phone/consent
are rechecked by the dispatcher just before calling Meta's Graph API.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.whatsapp.menus import main_menu, menu_reply
from app.core.config import settings
from app.models.user import User
from app.models.whatsapp_link import WhatsAppLink
from app.models.whatsapp_outbox import WhatsAppOutbox
from app.channels.whatsapp.events import InboundEnvelope


def _now() -> datetime:
    return datetime.now(timezone.utc)


def schedule_session_reply(
    db: Session, item: InboundEnvelope, *, link_completed: bool = False,
) -> bool:
    """Enqueue one response to one fresh signed inbound message.

    Meta's 24-hour window begins at the *actual message timestamp*, not
    webhook receipt. A synthetic sample without a timestamp never enables
    an outbound response or a service window.
    """
    if item.phone_number_id != settings.whatsapp_phone_number_id:
        return False
    if item.timestamp is None:
        return False
    now = _now()
    try:
        sent_at = datetime.fromtimestamp(item.timestamp, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return False
    # A small safety margin avoids responses close to service-window expiry.
    expires = sent_at + timedelta(hours=23, minutes=45)
    if sent_at > now + timedelta(minutes=2) or expires <= now:
        return False
    # SessionLocal has autoflush=False: newly completed links from this same
    # webhook transaction must be flushed before the read-back query.
    db.flush()
    linked = db.scalar(
        select(WhatsAppLink).where(
            WhatsAppLink.wa_id == item.sender_wa_id,
            WhatsAppLink.phone_number_id == item.phone_number_id,
            WhatsAppLink.consent_at.is_not(None),
            WhatsAppLink.verified_at.is_not(None),
            WhatsAppLink.revoked_at.is_(None),
        )
    )
    if linked is None:
        return False
    owner = db.get(User, linked.user_id)
    if not owner or owner.phone_e164 != "+" + item.sender_wa_id:
        return False

    # Only menu choices or explicit text solicit responses; never reply to
    # media or unsupported event types in this deliberately narrow product.
    if not link_completed and item.command is None:
        return False
    payload = (
        main_menu(linked.preferred_language)
        if link_completed else menu_reply(db, owner, linked.preferred_language, item.command)
    )
    db.add(WhatsAppOutbox(
        inbound_message_id=item.message_id,
        user_id=owner.id,
        recipient_wa_id=item.sender_wa_id,
        phone_number_id=item.phone_number_id,
        payload=payload,
        reply_before=expires,
    ))
    return True
