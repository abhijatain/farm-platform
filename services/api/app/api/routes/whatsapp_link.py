"""Firebase-protected WhatsApp linkage, consent and language management."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession
from app.channels.whatsapp.linking import current_link, request_link, revoke_link
from app.schemas.whatsapp_link import (
    StartWhatsAppLinkRequest,
    StartWhatsAppLinkResponse,
    WhatsAppLinkStatus,
)

router = APIRouter(prefix="/whatsapp/link", tags=["WhatsApp linking"])


@router.get("", response_model=WhatsAppLinkStatus)
def get_link_status(db: DBSession, current_user: CurrentUser) -> WhatsAppLinkStatus:
    return current_link(db, current_user)


@router.post("/start", response_model=StartWhatsAppLinkResponse)
def start_link(
    form: StartWhatsAppLinkRequest, db: DBSession, current_user: CurrentUser,
) -> StartWhatsAppLinkResponse:
    return request_link(db, current_user, form)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def unlink(db: DBSession, current_user: CurrentUser) -> None:
    revoke_link(db, current_user)
