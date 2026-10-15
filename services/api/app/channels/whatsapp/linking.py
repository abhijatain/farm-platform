"""Link a Firebase-authenticated farmer to their verified WhatsApp sender.

The two-channel proof combines authenticated Firebase phone ownership with
an unguessable, short-lived code received via a Meta-signed webhook from the
*same phone number*. Content is parsed in memory but never stored or logged.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.whatsapp_link import WhatsAppLink
from app.schemas.whatsapp_link import (
    StartWhatsAppLinkRequest,
    StartWhatsAppLinkResponse,
    WhatsAppLinkStatus,
)

LINK_TTL = timedelta(minutes=10)
CODE_PATTERN = re.compile(r"^LINK\s+([0-9a-fA-F]{20})$", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    # 20 cryptographically random hex digits = 80 bits; hashing additionally
    # prevents the database from exposing usable pending linking credentials.
    return hashlib.sha256(code.upper().encode("ascii")).hexdigest()


def _service_ready() -> None:
    if not settings.whatsapp_app_secret or not (
        settings.whatsapp_phone_number_id
        and settings.whatsapp_phone_number_id.isdigit()
    ):
        raise HTTPException(
            status_code=503, detail="WhatsApp linking not configured"
        )


def _valid_owner_phone(phone: str) -> bool:
    return bool(PHONE_PATTERN.fullmatch(phone))


def request_link(
    db: Session, user: User, form: StartWhatsAppLinkRequest
) -> StartWhatsAppLinkResponse:
    """Issue a one-time code after Firebase phone authentication and consent."""
    _service_ready()
    if not _valid_owner_phone(user.phone_e164):
        raise HTTPException(status_code=422, detail="Verified E.164 phone required")
    row = db.scalar(
        select(WhatsAppLink).where(WhatsAppLink.user_id == user.id).with_for_update()
    )
    if row is not None and row.verified_at and row.consent_at and row.wa_id:
        raise HTTPException(status_code=409, detail="WhatsApp already linked")
    now = _utcnow()
    code = secrets.token_hex(10).upper()
    if row is None:
        row = WhatsAppLink(user_id=user.id, preferred_language=form.preferred_language)
        db.add(row)
    row.wa_id = None
    row.phone_number_id = None
    row.code_hash = _hash_code(code)
    row.code_expires_at = now + LINK_TTL
    row.preferred_language = form.preferred_language
    row.verified_at = None
    row.consent_at = None
    row.revoked_at = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Please retry link setup") from None
    return StartWhatsAppLinkResponse(
        link_code=code,
        expires_at=now + LINK_TTL,
        instructions="From your Firebase-verified phone, send LINK followed by this code to our WhatsApp business number within 10 minutes.",
    )


def _revoke(row: WhatsAppLink) -> None:
    """Clear authorization state immediately, including unused code hashes."""
    row.wa_id = None
    row.phone_number_id = None
    row.code_hash = None
    row.code_expires_at = None
    row.verified_at = None
    row.consent_at = None
    row.revoked_at = _utcnow()


def revoke_link(db: Session, user: User) -> None:
    """Let the authenticated owner revoke consent and WhatsApp access."""
    row = db.scalar(
        select(WhatsAppLink).where(WhatsAppLink.user_id == user.id).with_for_update()
    )
    if row:
        _revoke(row)
        db.commit()


def invalidate_link_on_phone_change(db: Session, user: User) -> None:
    """Old phone ownership must not retain access after Firebase changes."""
    row = db.scalar(
        select(WhatsAppLink).where(WhatsAppLink.user_id == user.id).with_for_update()
    )
    if row:
        _revoke(row)


def current_link(db: Session, user: User) -> WhatsAppLinkStatus:
    row = db.scalar(select(WhatsAppLink).where(WhatsAppLink.user_id == user.id))
    if row is None:
        return WhatsAppLinkStatus(status="unlinked")
    if row.wa_id and row.verified_at and row.consent_at:
        return WhatsAppLinkStatus(
            status="linked", wa_id_last4=row.wa_id[-4:],
            preferred_language=row.preferred_language, consent_at=row.consent_at,
        )
    if row.code_hash and row.code_expires_at and row.code_expires_at > _utcnow():
        return WhatsAppLinkStatus(
            status="pending", preferred_language=row.preferred_language,
            code_expires_at=row.code_expires_at,
        )
    return WhatsAppLinkStatus(
        status="revoked" if row.revoked_at else "unlinked",
        preferred_language=row.preferred_language,
    )


def parse_link_code(text: str | None) -> str | None:
    """Extract only the exact LINK command; never retain other user messages."""
    if not isinstance(text, str) or len(text) > 100:
        return None
    match = CODE_PATTERN.fullmatch(text.strip())
    return match.group(1).upper() if match else None


def complete_link(
    db: Session, *, code: str, sender_wa_id: str, phone_number_id: str,
) -> bool:
    """Atomically consume a short-lived code after matching verified numbers.

    Must only be called from the correctly HMAC-signed webhook, and in the
    SAME transaction as the unique inbox event insert.
    """
    if (
        phone_number_id != settings.whatsapp_phone_number_id
        or not sender_wa_id.isdigit()
        or len(code) != 20
        or not all(ch in "0123456789ABCDEF" for ch in code)
    ):
        return False
    row = db.scalar(
        select(WhatsAppLink)
        .where(WhatsAppLink.code_hash == _hash_code(code))
        .with_for_update()
    )
    if not row or not row.code_expires_at or row.code_expires_at <= _utcnow():
        return False
    owner = db.get(User, row.user_id)
    if (
        not owner or not _valid_owner_phone(owner.phone_e164)
        or owner.phone_e164[1:] != sender_wa_id
        or row.wa_id or row.verified_at or row.consent_at
    ):
        return False
    if db.scalar(
        select(WhatsAppLink.id).where(
            WhatsAppLink.wa_id == sender_wa_id,
            WhatsAppLink.user_id != owner.id,
        )
    ):
        return False
    now = _utcnow()
    row.wa_id = sender_wa_id
    row.phone_number_id = phone_number_id
    row.code_hash = None
    row.code_expires_at = None
    row.verified_at = now
    row.consent_at = now
    row.revoked_at = None
    return True


def stop_messaging(db: Session, *, sender_wa_id: str, phone_number_id: str) -> bool:
    """Immediately honor signed inbound STOP even before automated replies exist."""
    if phone_number_id != settings.whatsapp_phone_number_id:
        return False
    row = db.scalar(
        select(WhatsAppLink).where(
            WhatsAppLink.wa_id == sender_wa_id,
            WhatsAppLink.phone_number_id == phone_number_id,
        ).with_for_update()
    )
    if not row:
        return False
    _revoke(row)
    return True
