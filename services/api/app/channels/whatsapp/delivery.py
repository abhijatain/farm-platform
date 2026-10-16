"""Apply signed Meta outbound delivery receipts without exposing message content.

Meta's Graph /messages response only confirms acceptance. Later messages
webhooks report delivery, read and asynchronous failed status for its wamid.
Never downgrade a read/delivered message if status callbacks arrive out of
order, and never resurrect failed jobs for automatic resend.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.whatsapp_outbox import WhatsAppOutbox

DELIVERY_RANK = {"sent": 1, "delivered": 2, "read": 3}


def update_delivery_receipts(db: Session, payload: object) -> int:
    """Apply only status updates from the configured receiving Meta phone ID."""
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return 0
    count = 0
    for entry in payload.get("entry", []):
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []):
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != settings.whatsapp_phone_number_id:
                continue
            for event in value.get("statuses", []):
                if not isinstance(event, dict):
                    continue
                mid, state = event.get("id"), event.get("status")
                if not isinstance(mid, str) or len(mid) > 255 or state not in {"sent", "delivered", "read", "failed"}:
                    continue
                job = db.scalar(
                    select(WhatsAppOutbox)
                    .where(
                        WhatsAppOutbox.meta_message_id == mid,
                        WhatsAppOutbox.phone_number_id == settings.whatsapp_phone_number_id,
                    )
                    .with_for_update()
                )
                if not job or job.status in {"cancelled", "pending", "sending"}:
                    continue
                if state == "failed":
                    # A late failure must not turn an already read reply into a
                    # retryable job or overwrite a confirmed delivery.
                    if job.status in {"sent", "failed"}:
                        job.status = "failed"
                        errors = event.get("errors")
                        code = errors[0].get("code") if isinstance(errors, list) and errors and isinstance(errors[0], dict) else None
                        job.last_error = f"Meta delivery code {code}" if isinstance(code, int) else "Meta delivery failed"
                        count += 1
                elif job.status != "failed" and DELIVERY_RANK.get(state, 0) > DELIVERY_RANK.get(job.status, 0):
                    job.status = state
                    count += 1
    return count
