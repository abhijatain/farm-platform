"""Send a user-initiated, service-window text reply through Meta Cloud API.

No templates, broadcasts, proactive alerts, or report links are supported in
this first milestone. Call only from the background worker, never a webhook.
"""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


class WhatsAppSendError(Exception):
    """Outbound provider rejected a request; never expose tokens in errors."""


def send_text(*, recipient: str, body: str) -> str:
    """Return Meta's accepted message ID, which is not delivery confirmation."""
    token = settings.whatsapp_access_token
    phone_id = settings.whatsapp_phone_number_id
    version = settings.whatsapp_graph_version
    if not token or not token.get_secret_value() or not phone_id:
        raise WhatsAppSendError("Missing WhatsApp sender credentials.")
    if not re.fullmatch(r"[0-9]{4,64}", phone_id):
        raise WhatsAppSendError("Invalid WhatsApp phone ID.")
    if not re.fullmatch(r"v[0-9]{1,2}\.[0-9]{1,2}", version):
        raise WhatsAppSendError("Invalid configured Graph API version.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{4,128}", recipient):
        raise WhatsAppSendError("Invalid WhatsApp recipient.")
    if not body or len(body) > 1000:
        raise WhatsAppSendError("Invalid reply length.")

    data = json.dumps({
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }, ensure_ascii=False).encode("utf-8")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            decoded = json.loads(response.read(32768))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Do not log or persist provider response, which may expose personal
        # identifiers or authentication context.
        raise WhatsAppSendError("WhatsApp provider request failed.") from None
    messages = decoded.get("messages", []) if isinstance(decoded, dict) else []
    external_id = messages[0].get("id") if messages and isinstance(messages[0], dict) else None
    if not isinstance(external_id, str) or not external_id:
        raise WhatsAppSendError("Provider did not return a message ID.")
    return external_id[:255]
