"""Security and parsing regressions for official Meta WhatsApp callbacks.

The integration is disabled without configured secrets. These tests use
synthetic metadata only and never send messages to external providers.
"""

import hashlib
import hmac

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.channels.whatsapp.events import incoming_envelopes
from app.channels.whatsapp.security import verify_handshake, verify_signature
from app.core.config import settings


def sign(body: bytes, secret: str = "test-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def configured_secrets(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_verify_token", SecretStr("test-verify-token"))
    monkeypatch.setattr(settings, "whatsapp_app_secret", SecretStr("test-secret"))


def test_handshake_requires_correct_token(configured_secrets):
    assert verify_handshake("subscribe", "test-verify-token", "13579") == "13579"
    with pytest.raises(HTTPException) as result:
        verify_handshake("subscribe", "wrong", "13579")
    assert result.value.status_code == 403
    with pytest.raises(HTTPException):
        verify_handshake("unsubscribe", "test-verify-token", "13579")


def test_missing_secrets_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_verify_token", None)
    monkeypatch.setattr(settings, "whatsapp_app_secret", None)
    with pytest.raises(HTTPException) as result:
        verify_handshake("subscribe", "anything", "123")
    assert result.value.status_code == 503
    with pytest.raises(HTTPException) as result:
        verify_signature(b"{}", sign(b"{}"))
    assert result.value.status_code == 503


def test_signature_checks_exact_bytes(configured_secrets):
    payload = b'{"object":"whatsapp_business_account"}'
    verify_signature(payload, sign(payload))
    for invalid in (None, "sha256=bad", "sha1=abcdef", sign(payload + b" ")):
        with pytest.raises(HTTPException) as result:
            verify_signature(payload, invalid)
        assert result.value.status_code == 403


def test_metadata_extraction_ignores_status_updates():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {"changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "12345"},
                    "statuses": [{"id": "wamid.status"}],
                    "messages": [
                        {"id": "wamid.first", "from": "919876543210", "type": "text", "text": {"body": "private"}},
                        {"id": "wamid.second", "from": "919876543210", "type": "image", "image": {"id": "secret"}},
                    ],
                },
            }]}
        ],
    }
    result = incoming_envelopes(payload)
    assert len(result) == 2
    assert {x.message_id for x in result} == {"wamid.first", "wamid.second"}
    assert result[0].phone_number_id == "12345"
    assert "private" not in repr(result)
    assert "secret" not in repr(result)


def test_invalid_or_nonwhatsapp_payload_not_processed():
    assert incoming_envelopes({"object": "other", "entry": []}) == []
    assert incoming_envelopes({"object": "whatsapp_business_account", "entry": []}) == []


def test_missing_number_or_sender_does_not_create_inbox_event():
    payload = {"object": "whatsapp_business_account", "entry": [{"changes": [
        {"field": "messages", "value": {"metadata": {}, "messages": [
            {"id": "wamid.valid", "from": "919876543210", "type": "text"}
        ]}}
    ]}]}
    assert incoming_envelopes(payload) == []
