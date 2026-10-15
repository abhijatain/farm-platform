"""Extract minimal WhatsApp metadata without storing farmer message content.

Statuses are delivery receipts, not inbound farmer messages. Text, photos,
location and audio are deliberately NOT processed until consent, identity
linking, durable dispatch and retention policy have been implemented.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class InboundEnvelope:
    message_id: str
    sender_wa_id: str
    phone_number_id: str
    message_type: str


def incoming_envelopes(payload: object) -> list[InboundEnvelope]:
    """Process only real inbound events for this subscribed account."""
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return []
    envelopes: list[InboundEnvelope] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata") or {}
            number_id = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            if not isinstance(number_id, str) or not number_id.isdigit() or len(number_id) > 40:
                continue
            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for item in messages:
                if not isinstance(item, dict):
                    continue
                mid, sender, kind = item.get("id"), item.get("from"), item.get("type")
                if (
                    isinstance(mid, str) and 5 <= len(mid) <= 255
                    and isinstance(sender, str) and sender.isdigit() and len(sender) <= 32
                    and isinstance(kind, str) and 1 <= len(kind) <= 30
                ):
                    envelopes.append(InboundEnvelope(mid, sender, number_id, kind))
    return envelopes
