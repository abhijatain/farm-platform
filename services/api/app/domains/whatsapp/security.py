"""Validate Meta webhook signatures and reject requests when not configured."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException

from app.core.config import settings


def configured_secret(name: str) -> str:
    """Never allow an empty token or secret to validate a public webhook."""
    secret = getattr(settings, name, None)
    value = secret.get_secret_value() if secret is not None else ""
    if not value:
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured.")
    return value


def verify_handshake(mode: str | None, token: str | None, challenge: str | None) -> str:
    """Echo only a valid Meta subscription challenge with a matching secret."""
    expected = configured_secret("whatsapp_verify_token")
    if (
        mode != "subscribe"
        or not token
        or not challenge
        or len(challenge) > 512
        or not hmac.compare_digest(token, expected)
    ):
        raise HTTPException(status_code=403, detail="Webhook verification failed.")
    return challenge


def verify_signature(payload: bytes, signature: str | None) -> None:
    """Meta signs raw POST bytes using X-Hub-Signature-256 and the App Secret."""
    secret = configured_secret("whatsapp_app_secret")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")
    provided = signature[7:]
    if len(provided) != 64 or any(x not in "0123456789abcdefABCDEF" for x in provided):
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")
    computed = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, provided.lower()):
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")
