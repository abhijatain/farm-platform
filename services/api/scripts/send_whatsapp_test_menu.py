"""Manually preview/send a WhatsApp interactive menu with Meta's test sender.

No webhook is forged, no farmer is linked, and no application DB rows are
created. This is an explicit, development-only demonstration of the outbound
Meta interactive-list payload, NOT an end-to-end linking test.

Run from services/api:
  uv run python scripts/send_whatsapp_test_menu.py
  uv run python scripts/send_whatsapp_test_menu.py --send
"""

from __future__ import annotations

import argparse
import re
import urllib.error
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.channels.whatsapp.menus import main_menu
from app.channels.whatsapp.outbox import _graph_error, _send_graph_message
from app.core.config import settings
from app.models.whatsapp_outbox import WhatsAppOutbox


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explicit Meta test-recipient interactive-menu smoke test."
    )
    parser.add_argument("--language", choices=("en", "hi", "pa"), default="en")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send one real WhatsApp interactive menu to a verified test recipient.",
    )
    args = parser.parse_args()

    if settings.environment != "development":
        parser.error("Available only in ENVIRONMENT=development.")

    menu = main_menu(args.language)
    rows = menu["interactive"]["action"]["sections"][0]["rows"]
    print("Farm Platform test menu preview:")
    for row in rows:
        print(" -", row["title"])
    print("This demonstration does not link a farmer or receive menu clicks.")

    if not args.send:
        print("Dry run only; pass --send for one explicit Meta sandbox message.")
        return

    if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
        parser.error("Configure the Meta test Phone Number ID and access token in services/api/.env.")

    print("Use this only with Meta's API Setup test sender and your verified test recipient.")
    recipient = input("Verified recipient phone in +country-number format: ").strip()
    if not re.fullmatch(r"\+[1-9]\d{7,14}", recipient):
        parser.error("Invalid international phone format.")
    if input("Type SEND TEST to send one interactive list: ").strip() != "SEND TEST":
        print("Cancelled without sending.")
        return

    # Construct an in-memory payload for the same Meta send helper used by
    # the worker; never persist it or simulate Firebase/WhatsApp linkage.
    job = WhatsAppOutbox(
        inbound_message_id="sandbox-" + uuid4().hex,
        user_id=uuid4(),
        recipient_wa_id=recipient[1:],
        phone_number_id=settings.whatsapp_phone_number_id,
        payload=menu,
        reply_before=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    try:
        _send_graph_message(job)
    except urllib.error.HTTPError as error:
        _, reason = _graph_error(error)
        print("Meta did not accept the message:", reason)
        raise SystemExit(1) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, RuntimeError):
        print("Failed to send the sandbox menu. Check Meta token and test recipient.")
        raise SystemExit(1) from None
    print("Meta accepted the sandbox menu. Confirm delivery on your test phone.")
    print("Interactive selections still require published-app inbound webhooks.")


if __name__ == "__main__":
    main()
