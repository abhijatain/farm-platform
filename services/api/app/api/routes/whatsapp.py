"""Public Meta WhatsApp webhooks with fail-closed signature verification.

GET establishes the subscription; POST verifies raw bytes before parsing and
only commits bounded, idempotent inbox events. No farmer records are returned.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.api.deps import DBSession
from app.core.config import settings
from app.domains.whatsapp.inbox import extract_messages, save_messages
from app.domains.whatsapp.security import verify_handshake, verify_signature


router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


@router.get("/webhook", include_in_schema=False)
def verify_webhook(request: Request) -> PlainTextResponse:
    params = request.query_params
    challenge = verify_handshake(
        params.get("hub.mode"),
        params.get("hub.verify_token"),
        params.get("hub.challenge"),
    )
    return PlainTextResponse(challenge)


@router.post("/webhook", include_in_schema=False)
async def ingest_webhook(request: Request, db: DBSession) -> dict[str, str]:
    # Verify signature on the exact bytes sent by Meta. Never parse untrusted
    # JSON first, and cap body size even if Content-Length is absent.
    if not settings.whatsapp_phone_number_id:
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured.")
    max_bytes = settings.whatsapp_max_webhook_bytes
    if max_bytes <= 0:
        raise HTTPException(status_code=503, detail="Invalid WhatsApp webhook configuration.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Webhook payload too large.")
    verify_signature(bytes(body), request.headers.get("X-Hub-Signature-256"))
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.") from None
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")
    items = extract_messages(parsed)
    if items:
        save_messages(db, items)
    # Always acknowledge valid status/delivery receipts too: they are not
    # farmer commands, and Meta retries on non-2xx status codes.
    return {"status": "accepted"}
