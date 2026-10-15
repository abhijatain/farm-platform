"""Normalize signed Meta inbound events and persist unique commands.

Webhook transactions only perform bounded database writes; they do not call
Meta, a model, satellite APIs, or user-specific farm services.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.whatsapp.conversation import normalized_command
from app.models.whatsapp import WhatsAppContact, WhatsAppInbound


WA_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{4,128}$")
PHONE_ID_PATTERN = re.compile(r"^[0-9]{4,64}$")


def extract_messages(payload: dict, *, now: datetime | None = None) -> list[dict]:
    """Accept only well-formed messages for our configured business phone ID."""
    if payload.get("object") != "whatsapp_business_account":
        return []
    phone_id = settings.whatsapp_phone_number_id
    if not phone_id or not PHONE_ID_PATTERN.fullmatch(phone_id):
        return []
    current = now or datetime.now(timezone.utc)
    found: list[dict] = []
    for entry in payload.get("entry", [])[:20]:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", [])[:20]:
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != phone_id:
                continue
            for item in value.get("messages", [])[:50]:
                if not isinstance(item, dict):
                    continue
                external_id = item.get("id")
                sender = item.get("from")
                ts = item.get("timestamp")
                if not isinstance(external_id, str) or not 1 <= len(external_id) <= 255:
                    continue
                if not isinstance(sender, str) or not WA_ID_PATTERN.fullmatch(sender):
                    continue
                try:
                    sent_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                except (ValueError, TypeError, OverflowError, OSError):
                    continue
                # Do not allow future-dated messages to extend the reply window.
                if sent_at > current:
                    continue
                text = (
                    item.get("text", {}).get("body")
                    if item.get("type") == "text" and isinstance(item.get("text"), dict)
                    else None
                )
                if item.get("type") == "button" and isinstance(item.get("button"), dict):
                    text = item["button"].get("payload")
                if item.get("type") == "interactive" and isinstance(item.get("interactive"), dict):
                    i = item["interactive"]
                    choice = i.get("button_reply") or i.get("list_reply")
                    if isinstance(choice, dict):
                        text = choice.get("id")
                found.append({
                    "phone_number_id": phone_id,
                    "external_id": external_id,
                    "wa_id": sender,
                    "sent_at": sent_at,
                    "command": normalized_command(text),
                })
                if len(found) >= 50:
                    return found
    return found


def save_messages(db: Session, items: list[dict]) -> int:
    """Store deduplicated commands and minimal identifiers atomically."""
    created = 0
    for item in items:
        db.execute(
            pg_insert(WhatsAppContact)
            .values(
                id=uuid4(),
                phone_number_id=item["phone_number_id"],
                wa_id=item["wa_id"],
                language="und",
                updates_opt_in=False,
            )
            .on_conflict_do_nothing(constraint="uq_whatsapp_contacts_phone_wa")
        )
        contact_id = db.scalar(
            select(WhatsAppContact.id)
            .where(
                WhatsAppContact.phone_number_id == item["phone_number_id"],
                WhatsAppContact.wa_id == item["wa_id"],
            )
        )
        result = db.execute(
            pg_insert(WhatsAppInbound)
            .values(
                id=uuid4(),
                phone_number_id=item["phone_number_id"],
                external_id=item["external_id"],
                contact_id=contact_id,
                command=item["command"],
                sent_at=item["sent_at"],
                state="pending",
            )
            .on_conflict_do_nothing(constraint="uq_whatsapp_inbound_phone_external")
            .returning(WhatsAppInbound.id)
        ).scalar_one_or_none()
        if result is not None:
            created += 1
            db.execute(
                update(WhatsAppContact)
                .where(WhatsAppContact.id == contact_id)
                .values(last_inbound_at=datetime.now(timezone.utc))
            )
    db.commit()
    return created
