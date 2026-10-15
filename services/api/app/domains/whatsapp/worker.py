"""CLI worker for durable WhatsApp onboarding replies, separate from FastAPI.

From services/api: uv run python -m app.domains.whatsapp.worker --once
Sending remains disabled until WhatsApp credentials are set and the operator
explicitly enables WHATSAPP_SENDING_ENABLED.
"""

from __future__ import annotations

import argparse
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.domains.whatsapp.queue import drain_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Process signed WhatsApp inbox events and reply queue.")
    parser.add_argument("--once", action="store_true", help="Drain current inbox/outbox and exit.")
    parser.add_argument("--poll-seconds", type=float, default=3.0, help="Seconds between polls (default: 3).")
    args = parser.parse_args()
    if not args.once and args.poll_seconds < 1:
        parser.error("poll-seconds must be >= 1.")
    if settings.whatsapp_sending_enabled and (
        not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id
    ):
        parser.error("Sending is enabled without complete sender credentials.")
    try:
        while True:
            with SessionLocal() as db:
                processed, attempted = drain_once(db)
            if processed or attempted:
                # No personal identifiers or message bodies are printed.
                print(f"WhatsApp: processed={processed} outbound_attempts={attempted}")
            if args.once:
                return
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("WhatsApp worker stopped.")


if __name__ == "__main__":
    main()
