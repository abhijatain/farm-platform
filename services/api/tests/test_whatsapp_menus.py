"""Integration tests for WhatsApp farm menus, owner boundaries and outbox.

No network requests are sent to Meta; test users and farms are isolated from
real Firebase identities, and all fixture records are cleaned up afterward.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.api.routes.whatsapp_webhook import receive_meta_webhook
from app.channels.whatsapp.events import incoming_envelopes
from app.channels.whatsapp.delivery import update_delivery_receipts
from app.channels.whatsapp.handler import schedule_session_reply
from app.channels.whatsapp.menus import list_message, main_menu, menu_reply
from app.channels.whatsapp.outbox import _valid_consent, dispatch_one, _send_graph_message, _graph_error, check_configuration, verify_meta_connection
from app.channels.whatsapp.linking import complete_link, request_link, stop_messaging
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.farm import Farm
from app.models.field import Field
from app.models.season import Season
from app.models.user import User
from app.models.whatsapp_inbound_event import WhatsAppInboundEvent
from app.models.whatsapp_link import WhatsAppLink
from app.models.whatsapp_outbox import WhatsAppOutbox
from app.channels.whatsapp import outbox as outbox_module
from app.schemas.whatsapp_link import StartWhatsAppLinkRequest


@pytest.fixture
def meta_config(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_app_secret", SecretStr("signed-test-secret"))
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")
    monkeypatch.setattr(settings, "whatsapp_access_token", SecretStr("not-a-real-access-token"))
    monkeypatch.setattr(settings, "whatsapp_outbound_enabled", False)


@pytest.fixture
def farmers(meta_config):
    with SessionLocal() as db:
        ids = []
        for prefix in ("Owner", "Other"):
            unique = uuid4()
            user = User(
                firebase_uid="wa-menu-" + unique.hex,
                phone_e164="+91" + str(unique.int % 10_000_000_000).zfill(10),
                preferred_language="en",
            )
            db.add(user)
            db.flush()
            farm = Farm(owner_user_id=user.id, name=prefix + " Farm")
            db.add(farm)
            db.flush()
            season = Season(
                farm_id=farm.id, name=prefix + " Season",
                started_on=date(2026, 7, 1), status="active",
            )
            field = Field(
                farm_id=farm.id, name=prefix + " Field",
                boundary=func.ST_GeomFromText(
                    "POLYGON((0 0,1 0,1 1,0 1,0 0))", 4326,
                ),
            )
            db.add_all([season, field])
            db.flush()
            ids.append((user.id, farm.id, season.id, field.id))
        db.commit()
        try:
            yield db, ids
        finally:
            db.rollback()
            # Delete created inbox/outbox rows before users, preserving FK safety.
            for uid, farm_id, _, _ in ids:
                owner = db.get(User, uid)
                if owner:
                    for out in db.scalars(
                        select(WhatsAppOutbox).where(WhatsAppOutbox.user_id == uid)
                    ).all():
                        db.delete(out)
                    for inbound in db.scalars(
                        select(WhatsAppInboundEvent).where(
                            WhatsAppInboundEvent.sender_wa_id == owner.phone_e164[1:]
                        )
                    ).all():
                        db.delete(inbound)
                    link = db.scalar(select(WhatsAppLink).where(WhatsAppLink.user_id == uid))
                    if link:
                        db.delete(link)
                    db.delete(owner)
            db.commit()


def _rows(payload):
    return payload["interactive"]["action"]["sections"][0]["rows"]


def _body(payload):
    if payload["type"] == "text":
        return payload["text"]["body"]
    return payload["interactive"]["body"]["text"]


@pytest.mark.parametrize("language", ["pa", "hi", "en"])
def test_multilingual_menu_is_valid_meta_interactive_list(language):
    menu = main_menu(language)
    assert menu["type"] == "interactive"
    assert menu["interactive"]["type"] == "list"
    assert [row["id"] for row in _rows(menu)] == [
        "menu:farms", "menu:seasons", "menu:fields"
    ]
    assert len(menu["interactive"]["action"]["button"]) <= 20
    assert all(len(row["title"]) <= 24 for row in _rows(menu))


def test_farm_season_field_menu_paths_authorize_every_selection(farmers):
    db, ids = farmers
    owner = db.get(User, ids[0][0])
    farm_id, season_id, field_id = ids[0][1:]
    other_farm_id, other_season_id, other_field_id = ids[1][1:]
    farms = menu_reply(db, owner, "en", "1")
    assert _rows(farms)[0]["id"] == f"farm:{farm_id}"
    assert "Other Farm" not in str(farms)
    choices = menu_reply(db, owner, "en", f"farm:{farm_id}")
    assert _rows(choices)[0]["id"] == f"s-farm:{farm_id}"
    seasons = menu_reply(db, owner, "hi", f"s-farm:{farm_id}")
    assert _rows(seasons)[0]["id"] == f"season:{season_id}"
    fields = menu_reply(db, owner, "pa", f"f-farm:{farm_id}")
    assert _rows(fields)[0]["id"] == f"field:{field_id}"
    assert "Owner Season" in _body(menu_reply(db, owner, "en", f"season:{season_id}"))
    assert "Owner Field" in _body(menu_reply(db, owner, "en", f"field:{field_id}"))
    for stolen in (
        f"farm:{other_farm_id}", f"s-farm:{other_farm_id}",
        f"f-farm:{other_farm_id}", f"season:{other_season_id}",
        f"field:{other_field_id}", f"children:fields:{other_farm_id}:1",
    ):
        assert menu_reply(db, owner, "en", stolen) == main_menu("en")


def test_invalid_commands_and_empty_children_are_safe(farmers):
    db, ids = farmers
    user = db.get(User, ids[0][0])
    for command in ("../../other", "SELECT * FROM users", "field:123", None):
        assert menu_reply(db, user, "en", command) == main_menu("en")
    assert len(_rows(menu_reply(db, user, "pa", "menu:farms"))) <= 10


def _signed_request(phone: str, message_id: str, command: str, *, kind="text"):
    content = (
        {"type": "interactive", "interactive": {
            "type": "list_reply", "list_reply": {"id": command, "title": "Farms"},
        }}
        if kind == "interactive" else
        {"type": "text", "text": {"body": command}}
    )
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {
            "metadata": {"phone_number_id": "1234567890"},
            "messages": [{
                "id": message_id,
                "from": phone,
                "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                **content,
            }],
        }}]}],
    }

    class Request:
        async def body(self):
            return json.dumps(payload, separators=(",", ":")).encode()
        async def json(self):
            return payload

    req = Request()
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signed = "sha256=" + hmac.new(b"signed-test-secret", raw, hashlib.sha256).hexdigest()
    return req, signed


def test_signed_link_queues_welcome_and_menu_commands_are_idempotent(farmers):
    db, ids = farmers
    owner = db.get(User, ids[0][0])
    code = request_link(
        db, owner, StartWhatsAppLinkRequest(consent=True, preferred_language="pa"),
    ).link_code
    sender = owner.phone_e164[1:]
    msgid = "wamid.link-" + uuid4().hex
    req, sig = _signed_request(sender, msgid, "LINK " + code)
    assert asyncio.run(receive_meta_webhook(req, db, sig)) == {"status": "received"}
    welcome = db.scalar(
        select(WhatsAppOutbox).where(WhatsAppOutbox.inbound_message_id == msgid)
    )
    assert welcome is not None
    assert welcome.payload["type"] == "interactive"
    assert welcome.status == "pending"
    assert welcome.recipient_wa_id == sender
    assert asyncio.run(receive_meta_webhook(req, db, sig)) == {"status": "received"}
    assert db.scalars(select(WhatsAppOutbox).where(
        WhatsAppOutbox.inbound_message_id == msgid,
    )).all() == [welcome]

    second = "wamid.menu-" + uuid4().hex
    req, sig = _signed_request(sender, second, "menu:farms", kind="interactive")
    asyncio.run(receive_meta_webhook(req, db, sig))
    farm_response = db.scalar(
        select(WhatsAppOutbox).where(WhatsAppOutbox.inbound_message_id == second)
    )
    assert farm_response is not None
    assert _rows(farm_response.payload)[0]["id"] == f"farm:{ids[0][1]}"
    assert "Other Farm" not in str(farm_response.payload)


def test_menu_does_not_queue_for_unlinked_sender(farmers):
    db, ids = farmers
    owner = db.get(User, ids[0][0])
    req, sig = _signed_request(owner.phone_e164[1:], "wamid.unknown-" + uuid4().hex, "1")
    asyncio.run(receive_meta_webhook(req, db, sig))
    assert db.scalar(select(WhatsAppOutbox).where(
        WhatsAppOutbox.recipient_wa_id == owner.phone_e164[1:],
    )) is None


def test_outbound_is_disabled_by_default_and_invalid_without_consent(farmers):
    db, ids = farmers
    owner = db.get(User, ids[0][0])
    assert dispatch_one() == "disabled"
    job = WhatsAppOutbox(
        inbound_message_id="wamid.fake-" + uuid4().hex,
        user_id=owner.id, recipient_wa_id=owner.phone_e164[1:],
        phone_number_id="1234567890", payload=main_menu("en"),
        reply_before=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(job)
    db.commit()
    assert not _valid_consent(db, job)


def test_interactive_parser_extracts_reply_id_not_untrusted_title():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {
            "metadata": {"phone_number_id": "1234567890"},
            "messages": [{
                "id": "wamid.interactive", "from": "919000000001",
                "timestamp": "1790000000", "type": "interactive",
                "interactive": {"type": "list_reply", "list_reply": {
                    "id": "menu:farms", "title": "Untrusted label",
                }},
            }],
        }}]}],
    }
    envelope = incoming_envelopes(payload)[0]
    assert envelope.command == "menu:farms"
    assert envelope.timestamp == 1790000000
    assert "Untrusted label" not in repr(envelope)


def test_graph_api_interactive_list_payload_uses_official_schema(meta_config, monkeypatch):
    """Verify the real JSON body without contacting Meta or printing a token."""
    job = WhatsAppOutbox(
        inbound_message_id="wamid.payload-" + uuid4().hex,
        user_id=uuid4(), recipient_wa_id="919000000001",
        phone_number_id="1234567890",
        payload=main_menu("hi"), reply_before=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    def intercept(req, timeout):
        assert timeout <= 15
        assert req.full_url == "https://graph.facebook.com/v26.0/1234567890/messages"
        assert req.get_header("Authorization") == "Bearer not-a-real-access-token"
        data = json.loads(req.data)
        assert data["to"] == "919000000001"
        assert data["type"] == "interactive"
        assert data["interactive"]["type"] == "list"
        assert data["messaging_product"] == "whatsapp"
        return io.BytesIO(b'{"messages":[{"id":"wamid.fake123"}]}')

    monkeypatch.setattr(outbox_module.urllib.request, "urlopen", intercept)
    assert _send_graph_message(job) == "wamid.fake123"


def test_dispatcher_sends_only_after_linked_consent(farmers, monkeypatch):
    db, ids = farmers
    owner = db.get(User, ids[0][0])
    code = request_link(
        db, owner, StartWhatsAppLinkRequest(consent=True, preferred_language="en"),
    ).link_code
    assert complete_link(
        db, code=code, sender_wa_id=owner.phone_e164[1:],
        phone_number_id="1234567890",
    )
    db.commit()
    monkeypatch.setattr(settings, "whatsapp_outbound_enabled", True)
    inbound_id = "wamid.dispatch-" + uuid4().hex
    from app.channels.whatsapp.events import InboundEnvelope

    assert schedule_session_reply(db, InboundEnvelope(
        message_id=inbound_id, sender_wa_id=owner.phone_e164[1:],
        phone_number_id="1234567890", message_type="text",
        command="MENU", timestamp=int(datetime.now(timezone.utc).timestamp()),
    ))
    db.commit()
    outgoing = []
    def mock_send(job):
        outgoing.append(job.inbound_message_id)
        return "wamid.mock-outbound"
    monkeypatch.setattr(outbox_module, "_send_graph_message", mock_send)
    assert dispatch_one() == "sent"
    db.expire_all()
    item = db.scalar(select(WhatsAppOutbox).where(
        WhatsAppOutbox.inbound_message_id == inbound_id,
    ))
    assert item.status == "sent"
    assert item.meta_message_id == "wamid.mock-outbound"
    assert outgoing == [inbound_id]

    # A still-queued message must not be sent after revoking WhatsApp consent.
    revoked_id = "wamid.revoked-" + uuid4().hex
    assert schedule_session_reply(db, InboundEnvelope(
        message_id=revoked_id, sender_wa_id=owner.phone_e164[1:],
        phone_number_id="1234567890", message_type="text",
        command="1", timestamp=int(datetime.now(timezone.utc).timestamp()),
    ))
    db.commit()
    assert stop_messaging(
        db, sender_wa_id=owner.phone_e164[1:],
        phone_number_id="1234567890",
    )
    db.commit()
    assert dispatch_one() == "cancelled"
    assert outgoing == [inbound_id]


def _meta_receipt(msg_id, status, business_id="1234567890", errors=None):
    event = {"id": msg_id, "status": status}
    if errors is not None:
        event["errors"] = errors
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {
            "metadata": {"phone_number_id": business_id},
            "statuses": [event],
        }}]}],
    }


def test_meta_delivery_receipts_respect_account_and_order(farmers):
    db, ids = farmers
    user = db.get(User, ids[0][0])
    msg_id = "wamid.receipt-" + uuid4().hex
    row = WhatsAppOutbox(
        inbound_message_id="wamid.replied-" + uuid4().hex,
        user_id=user.id, recipient_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890", payload=main_menu("pa"),
        reply_before=datetime.now(timezone.utc) + timedelta(hours=1),
        meta_message_id=msg_id, status="sent",
    )
    db.add(row)
    db.commit()
    assert update_delivery_receipts(db, _meta_receipt(msg_id, "read", "999")) == 0
    assert row.status == "sent"
    assert update_delivery_receipts(db, _meta_receipt(msg_id, "delivered")) == 1
    assert row.status == "delivered"
    assert update_delivery_receipts(db, _meta_receipt(msg_id, "sent")) == 0
    assert update_delivery_receipts(db, _meta_receipt(msg_id, "read")) == 1
    assert row.status == "read"
    assert update_delivery_receipts(db, _meta_receipt(msg_id, "failed", errors=[{"code": 131026}])) == 0
    assert row.status == "read"
    db.commit()


def test_meta_async_failure_records_only_safe_code(farmers):
    db, ids = farmers
    user = db.get(User, ids[0][0])
    msg_id = "wamid.fail-" + uuid4().hex
    job = WhatsAppOutbox(
        inbound_message_id="wamid.sent-" + uuid4().hex,
        user_id=user.id, recipient_wa_id=user.phone_e164[1:],
        phone_number_id="1234567890", payload=main_menu("en"),
        reply_before=datetime.now(timezone.utc) + timedelta(hours=1),
        meta_message_id=msg_id, status="sent",
    )
    db.add(job)
    db.commit()
    event = _meta_receipt(msg_id, "failed", errors=[{
        "code": 131047,
        "message": "Private farmer data which must not be logged",
    }])
    assert update_delivery_receipts(db, event) == 1
    assert job.status == "failed"
    assert job.last_error == "Meta delivery code 131047"
    db.commit()


def test_outbox_check_mode_does_not_send_or_reveal_credentials(meta_config):
    state = check_configuration()
    assert state == {
        "signature_secret": True,
        "verify_token": bool(settings.whatsapp_verify_token),
        "phone_number_id": True,
        "access_token": True,
        "outbound_enabled": False,
    }
    assert "not-a-real-access-token" not in str(state)


def test_meta_sync_error_code_classifies_retry_safely():
    import urllib.error
    err = urllib.error.HTTPError(
        "https://graph.facebook.com/example", 400, "bad request", {},
        io.BytesIO(b'{"error":{"code":131056,"message":"private contact"}}'),
    )
    assert _graph_error(err) == (True, "Meta error 131056 (HTTP 400)")
    err = urllib.error.HTTPError(
        "https://graph.facebook.com/example", 400, "bad request", {},
        io.BytesIO(b'{"error":{"code":131026,"message":"private contact"}}'),
    )
    assert _graph_error(err) == (False, "Meta error 131026 (HTTP 400)")


def test_meta_receipt_parser_does_not_raise_on_malformed_envelopes():
    for payload in (
        None, "random", {"object": "whatsapp_business_account", "entry": None},
        {"object": "whatsapp_business_account", "entry": [{}]},
        {"object": "whatsapp_business_account", "entry": [{"changes": None}]},
        {"object": "whatsapp_business_account", "entry": [{"changes": [
            {"field": "messages", "value": {"metadata": {"phone_number_id": "1234567890"}, "statuses": None}}
        ]}]},
    ):
        assert update_delivery_receipts(None, payload) == 0


def test_meta_connection_check_only_makes_get_and_keeps_token_private(meta_config, monkeypatch):
    def fake_get(req, timeout):
        assert req.get_method() == "GET"
        assert timeout <= 10
        assert req.full_url.endswith("/1234567890?fields=id")
        assert req.get_header("Authorization") == "Bearer not-a-real-access-token"
        return io.BytesIO(b'{"id":"1234567890"}')

    monkeypatch.setattr(outbox_module.urllib.request, "urlopen", fake_get)
    result = verify_meta_connection()
    assert result == "Meta connection: OK (sending still requires permission)"
    assert "not-a-real-access-token" not in result
