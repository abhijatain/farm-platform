from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DBSession) -> User:
    """
    Temporary development authentication.

    Later this function will be replaced by Firebase ID-token
    verification. Routes should never accept owner_user_id from
    the client.
    """

    user = db.scalar(
        select(User).where(
            User.firebase_uid == settings.dev_firebase_uid
        )
    )

    if user is not None:
        return user

    user = User(
        firebase_uid=settings.dev_firebase_uid,
        phone_e164=settings.dev_phone_e164,
        name=settings.dev_user_name,
        preferred_language="en",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
