"""Verify WhatsApp Cloud API handshake and signed webhook payloads.

Reject unconfigured endpoints, use timing-safe comparisons and verify against
the raw body before JSON parsing. Never log the app secret or message payload.
"""

import hashlib
import hmac

from fastapi import HTTPException, status

from app.core.config import settings


def configured() -> bool:
    return bool(
        settings.whatsapp_verify_token
        and settings.whatsapp_app_secret
    )


def verify_handshake(mode: str | None, token: str | None, challenge: str | None) -> str:
    """Accept Meta's subscription verification only with the configured secret."""
    expected = settings.whatsapp_verify_token
    if not expected:
        raise HTTPException(status_code=503, detail="WhatsApp integration disabled")
    if (
        mode != "subscribe"
        or not token
        or not hmac.compare_digest(token.encode(), expected.get_secret_value().encode())
        or challenge is None
    ):
        raise HTTPException(status_code=403, detail="Invalid WhatsApp verification")
    return challenge


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    """Reject unsigned payloads before parsing or persisting any metadata."""
    secret = settings.whatsapp_app_secret
    if not secret:
        raise HTTPException(status_code=503, detail="WhatsApp integration disabled")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    expected = hmac.new(
        secret.get_secret_value().encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature[len("sha256="):]
    if len(provided) != 64 or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
