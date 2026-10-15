"""Receive verified Meta WhatsApp webhook events with idempotent DB writes.

This is an ingress foundation, NOT a conversational bot: it never sends
messages, interprets agriculture questions or links a WhatsApp phone to a farm.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.channels.whatsapp.events import incoming_envelopes
from app.channels.whatsapp.security import verify_handshake, verify_signature
from app.api.deps import DBSession
from app.models.whatsapp_inbound_event import WhatsAppInboundEvent

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp webhook"])


@router.get("", response_class=PlainTextResponse)
def verify_meta_subscription(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> str:
    return verify_handshake(mode, token, challenge)


@router.post("")
async def receive_meta_webhook(
    request: Request,
    db: DBSession,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    body = await request.body()
    # Meta signs the precise payload bytes, including whitespace and ordering.
    verify_signature(body, x_hub_signature_256)
    if len(body) > 512_000:
        raise HTTPException(status_code=413, detail="Webhook payload too large")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    envelopes = incoming_envelopes(payload)
    if len(envelopes) > 100:
        raise HTTPException(status_code=413, detail="Too many messages")

    # A unique message ID turns Meta webhook retries into no-ops.
    for item in envelopes:
        stmt = pg_insert(WhatsAppInboundEvent).values(
            message_id=item.message_id,
            sender_wa_id=item.sender_wa_id,
            phone_number_id=item.phone_number_id,
            message_type=item.message_type,
        ).on_conflict_do_nothing(index_elements=["message_id"])
        db.execute(stmt)
    db.commit()
    return {"status": "received"}
