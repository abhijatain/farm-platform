"""DB-backed tests for Firebase-to-WhatsApp consent, verification, and revocation.

CI's fresh PostGIS database exercises actual PostgreSQL uniqueness and
transaction behavior, not a mock identity database.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select

from app.api.routes.whatsapp_webhook import receive_meta_webhook
from app.channels.whatsapp.events import incoming_envelopes
from app.channels.whatsapp.linking import (
    _utcnow,
    complete_link,
    current_link,
    invalidate_link_on_phone_change,
    parse_link_code,
    request_link,
    revoke_link,
    stop_messaging,
)
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.whatsapp_inbound_event import WhatsAppInboundEvent
from app.models.whatsapp_link import WhatsAppLink
from app.schemas.whatsapp_link import StartWhatsAppLinkRequest


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_app_secret", SecretStr("unit-test-app-secret"))
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")


@pytest.fixture
def farmer(configured):
    with SessionLocal() as db:
        uid = uuid4()
        phone = "+91" + str(uid.int % 10_000_000_000).zfill(10)
        user = User(
            firebase_uid="whatsapp-link-test-" + uid.hex,
            phone_e164=phone,
            preferred_language="en",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        try:
            yield db, user
        finally:
            db.rollback()
            row = db.scalar(select(WhatsAppLink).where(WhatsAppLink.user_id == user.id))
            if row:
                db.delete(row)
                db.commit()
            # Remove signed synthetic event records before dropping the user.
            for event in db.scalars(
                select(WhatsAppInboundEvent).where(
                    WhatsAppInboundEvent.sender_wa_id == phone[1:]
                )
            ).all():
                db.delete(event)
            db.delete(user)
            db.commit()


def start(db, user, lang="pa"):
    return request_link(
        db, user, StartWhatsAppLinkRequest(consent=True, preferred_language=lang)
    )


def test_code_issuance_requires_opt_in_and_keeps_only_hash(farmer):
    db, user = farmer
    response = start(db, user)
    assert len(response.link_code) == 20
    assert response.link_code.isalnum()
    assert current_link(db, user).status == "pending"
    assert current_link(db, user).preferred_language == "pa"
    row = db.scalar(select(WhatsAppLink).where(WhatsAppLink.user_id == user.id))
    assert row.code_hash != response.link_code
    assert len(row.code_hash) == 64
    assert row.wa_id is None
    assert row.consent_at is None
    with pytest.raises(Exception):
        StartWhatsAppLinkRequest(consent=False, preferred_language="en")
    with pytest.raises(Exception):
        StartWhatsAppLinkRequest(consent=True, preferred_language="fr")


def test_only_matching_verified_whatsapp_phone_can_link(farmer):
    db, user = farmer
    code = start(db, user).link_code
    assert not complete_link(
        db, code=code, sender_wa_id="911234567890", phone_number_id="1234567890"
    )
    assert not complete_link(
        db, code=code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="other-business-number",
    )
    assert complete_link(
        db, code=code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )
    db.commit()
    status = current_link(db, user)
    assert status.status == "linked"
    assert status.wa_id_last4 == user.phone_e164[-4:]
    assert status.consent_at is not None
    assert not complete_link(
        db, code=code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )
    with pytest.raises(HTTPException) as error:
        start(db, user)
    assert error.value.status_code == 409


def test_expiration_and_revocation(farmer):
    db, user = farmer
    code = start(db, user).link_code
    link = db.scalar(select(WhatsAppLink).where(WhatsAppLink.user_id == user.id))
    link.code_expires_at = _utcnow() - timedelta(seconds=1)
    db.commit()
    assert current_link(db, user).status == "unlinked"
    assert not complete_link(
        db, code=code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )
    code = start(db, user).link_code
    revoke_link(db, user)
    assert current_link(db, user).status == "revoked"
    assert not complete_link(
        db, code=code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )


def test_stop_and_firebase_phone_change_both_revoke(farmer):
    db, user = farmer
    code = start(db, user, "hi").link_code
    assert complete_link(
        db, code=code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )
    db.commit()
    assert stop_messaging(
        db, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )
    db.commit()
    assert current_link(db, user).status == "revoked"
    second_code = start(db, user).link_code
    assert complete_link(
        db, code=second_code, sender_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890",
    )
    db.commit()
    invalidate_link_on_phone_change(db, user)
    db.commit()
    assert current_link(db, user).status == "revoked"


def test_link_command_extraction_does_not_store_arbitrary_text():
    code = "AB" * 10
    assert parse_link_code(f"link {code.lower()}") == code
    assert parse_link_code("normal farmer question") is None
    assert parse_link_code("LINK short") is None
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "1234567890"},
                    "messages": [
                        {"id": "wamid.mocktest", "from": "919876543210", "type": "text",
                         "text": {"body": "LINK " + code}},
                        {"id": "wamid.stoptest", "from": "919876543210", "type": "text",
                         "text": {"body": "STOP"}},
                        {"id": "wamid.private", "from": "919876543210", "type": "text",
                         "text": {"body": "My field is sick"}},
                    ],
                },
            }],
        }],
    }
    events = incoming_envelopes(payload)
    assert events[0].link_code == code
    assert events[1].opt_out is True
    assert events[2].link_code is None
    assert "ABABABAB" not in repr(events)
    assert "My field is sick" not in repr(events)


def test_invalid_phone_or_configuration_rejected(farmer, monkeypatch):
    db, user = farmer
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", None)
    with pytest.raises(HTTPException) as error:
        start(db, user)
    assert error.value.status_code == 503


class _SignedRequest:
    def __init__(self, payload):
        self.payload = payload
        self.raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    async def body(self):
        return self.raw

    async def json(self):
        return self.payload


def test_signed_meta_webhook_links_atomically_and_ignores_replay(farmer):
    db, user = farmer
    code = start(db, user).link_code
    message_id = "wamid.test-" + uuid4().hex
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "1234567890"},
                    "messages": [{
                        "id": message_id, "from": user.phone_e164[1:],
                        "type": "text", "text": {"body": "LINK " + code},
                    }],
                },
            }],
        }],
    }
    req = _SignedRequest(payload)
    sig = "sha256=" + hmac.new(
        b"unit-test-app-secret", req.raw, hashlib.sha256
    ).hexdigest()
    assert asyncio.run(receive_meta_webhook(req, db, sig)) == {"status": "received"}
    assert current_link(db, user).status == "linked"
    # Replays of the same Meta message do not change link or consent state.
    assert asyncio.run(receive_meta_webhook(req, db, sig)) == {"status": "received"}
    assert db.scalar(
        select(WhatsAppInboundEvent).where(WhatsAppInboundEvent.message_id == message_id)
    ) is not None
    # A second signed webhook with STOP revokes the previously authorized link.
    stop = _SignedRequest({
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {
            "metadata": {"phone_number_id": "1234567890"},
            "messages": [{"id": "wamid.stop-" + uuid4().hex, "from": user.phone_e164[1:],
                          "type": "text", "text": {"body": "STOP"}}]
        }}]}],
    })
    stop_sig = "sha256=" + hmac.new(
        b"unit-test-app-secret", stop.raw, hashlib.sha256
    ).hexdigest()
    asyncio.run(receive_meta_webhook(stop, db, stop_sig))
    assert current_link(db, user).status == "revoked"
