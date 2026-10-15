"""Dispatch queued WhatsApp session replies using Meta's official Cloud API.

Run as a *separate* worker process; the signed webhook never waits for Meta.
Sending is disabled by default and requires an explicitly enabled, supported
Meta business account and a server-side access token. This is NOT a broadcast
sender: outbound recipients must still hold active Firebase-linked consent.

Delivery is at-least-once if the process crashes after Meta accepts a send
but before the DB commits the receipt. Do not use this for money transfers
or activities; its only payloads are read-only menus and field summaries.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.models.whatsapp_link import WhatsAppLink
from app.models.whatsapp_outbox import WhatsAppOutbox

MAX_ATTEMPTS = 5
LEASE = timedelta(minutes=3)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _send_graph_message(job: WhatsAppOutbox) -> str:
    """POST an owner-authorized outbound message using a private Meta token."""
    token = settings.whatsapp_access_token
    version = settings.whatsapp_graph_version
    if not token or not re.fullmatch(r"v\d{1,2}\.\d", version):
        raise RuntimeError("Missing WhatsApp access token or invalid Graph version")
    if not (job.phone_number_id.isdigit() and job.recipient_wa_id.isdigit()):
        raise ValueError("Invalid Meta phone identifiers")
    endpoint = f"https://graph.facebook.com/{version}/{job.phone_number_id}/messages"
    request_body = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": job.recipient_wa_id,
        **job.payload,
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=request_body,
        headers={
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # Never log the request, URL params, recipient phone or bearer token.
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    message_id = data.get("messages", [{}])[0].get("id")
    if not isinstance(message_id, str) or not message_id.startswith("wamid"):
        raise RuntimeError("Meta did not return an outbound message ID")
    return message_id


def _claim(db: Session) -> WhatsAppOutbox | None:
    """Lease a job transactionally, including timed-out abandoned leases."""
    now = _utcnow()
    stmt = (
        select(WhatsAppOutbox)
        .where(
            WhatsAppOutbox.attempts < MAX_ATTEMPTS,
            or_(
                and_(
                    WhatsAppOutbox.status == "pending",
                    WhatsAppOutbox.available_at <= now,
                ),
                and_(
                    WhatsAppOutbox.status == "sending",
                    WhatsAppOutbox.lease_until <= now,
                ),
            ),
        )
        .order_by(WhatsAppOutbox.created_at, WhatsAppOutbox.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.scalar(stmt)
    if job is not None:
        job.status = "sending"
        job.attempts += 1
        job.lease_until = now + LEASE
        db.commit()
    return job


def _valid_consent(db: Session, job: WhatsAppOutbox) -> bool:
    """Recheck authorization and service window immediately before dispatch."""
    if not settings.whatsapp_outbound_enabled:
        return False
    if (
        not settings.whatsapp_access_token
        or job.phone_number_id != settings.whatsapp_phone_number_id
        or _utcnow() >= job.reply_before
    ):
        return False
    link = db.scalar(select(WhatsAppLink).where(
        WhatsAppLink.user_id == job.user_id,
        WhatsAppLink.wa_id == job.recipient_wa_id,
        WhatsAppLink.phone_number_id == job.phone_number_id,
        WhatsAppLink.consent_at.is_not(None),
        WhatsAppLink.verified_at.is_not(None),
        WhatsAppLink.revoked_at.is_(None),
    ))
    if link is None:
        return False
    owner = db.get(User, job.user_id)
    return owner is not None and owner.phone_e164 == "+" + job.recipient_wa_id


def dispatch_one() -> str:
    """Process at most one queued item; return a non-sensitive outcome."""
    if not settings.whatsapp_outbound_enabled or not settings.whatsapp_access_token:
        return "disabled"
    with SessionLocal() as db:
        job = _claim(db)
        if job is None:
            return "idle"
        if not _valid_consent(db, job):
            job.status = "cancelled"
            job.lease_until = None
            db.commit()
            return "cancelled"
        try:
            message_id = _send_graph_message(job)
        except urllib.error.HTTPError as error:
            # Do not persist or print Meta's error body: it may contain PII.
            retryable = error.code in {408, 429} or error.code >= 500
            return _record_failure(db, job, retryable, "Meta HTTP response")
        except (urllib.error.URLError, TimeoutError, OSError):
            return _record_failure(db, job, True, "Meta connectivity")
        except (ValueError, RuntimeError, KeyError, IndexError, TypeError):
            return _record_failure(db, job, False, "Meta invalid response")
        job.status = "sent"
        job.meta_message_id = message_id
        job.sent_at = _utcnow()
        job.lease_until = None
        job.last_error = None
        db.commit()
        return "sent"


def _record_failure(db: Session, job: WhatsAppOutbox, retry: bool, reason: str) -> str:
    job.last_error = reason
    job.lease_until = None
    if retry and job.attempts < MAX_ATTEMPTS and _utcnow() < job.reply_before:
        job.status = "pending"
        job.available_at = _utcnow() + timedelta(seconds=min(300, 15 * 2 ** job.attempts))
        result = "retry"
    else:
        job.status = "failed"
        result = "failed"
    db.commit()
    return result


def main() -> None:
    """Run a single dispatch for local testing, or poll continuously."""
    parser = argparse.ArgumentParser(description="Meta WhatsApp session outbox worker")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Process at most one message")
    mode.add_argument("--loop", action="store_true", help="Poll the outbox until stopped")
    args = parser.parse_args()
    if args.once:
        print(dispatch_one())
        return
    while True:
        state = dispatch_one()
        # No request bodies, tokens, phone numbers or farm names in logs.
        if state not in {"idle", "disabled"}:
            print(state, flush=True)
        time.sleep(2 if state != "disabled" else 15)


if __name__ == "__main__":
    main()
