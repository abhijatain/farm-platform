"""Authenticated WhatsApp-link request, one-time code and status contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["pa", "hi", "en"]


class StartWhatsAppLinkRequest(BaseModel):
    # Consent means service messaging only; marketing requires separate opt-in.
    consent: Literal[True]
    preferred_language: Language


class StartWhatsAppLinkResponse(BaseModel):
    link_code: str = Field(description="One-time secret; display once and never log")
    expires_at: datetime
    instructions: str
    business_phone_e164: str | None = None


class WhatsAppLinkStatus(BaseModel):
    status: Literal["unlinked", "pending", "linked", "revoked"]
    preferred_language: Language | None = None
    wa_id_last4: str | None = None
    consent_at: datetime | None = None
    code_expires_at: datetime | None = None
