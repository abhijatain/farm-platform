"""Expose the authenticated farmer identity and profile."""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models.user import User
from app.schemas.user import CurrentUserResponse


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_me(
    current_user: CurrentUser,
) -> User:
    return current_user
