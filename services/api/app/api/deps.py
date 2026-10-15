"""Resolve Firebase identities and database sessions for authenticated requests."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from firebase_admin import auth
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.channels.whatsapp.linking import invalidate_link_on_phone_change
from app.core.firebase import get_firebase_app
from app.db.session import SessionLocal
from app.models.user import User


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[
    Session,
    Depends(get_db),
]


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------

bearer_scheme = HTTPBearer(
    auto_error=False
)


def authentication_error(
    detail: str = "Invalid or expired authentication token.",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def get_current_user(
    db: DBSession,
    authorization: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> User:

    # -----------------------------------------------------
    # REQUIRE BEARER TOKEN
    # -----------------------------------------------------

    if authorization is None:
        raise authentication_error(
            "Authentication required."
        )

    if authorization.scheme.lower() != "bearer":
        raise authentication_error()

    id_token = authorization.credentials

    # -----------------------------------------------------
    # VERIFY FIREBASE TOKEN
    # -----------------------------------------------------

    try:
        firebase_app = get_firebase_app()

        decoded_token = auth.verify_id_token(
            id_token,
            app=firebase_app,
        )

    except (
        auth.InvalidIdTokenError,
        auth.ExpiredIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        auth.CertificateFetchError,
        ValueError,
    ):
        raise authentication_error()

    # -----------------------------------------------------
    # FIREBASE UID
    # -----------------------------------------------------

    firebase_uid = decoded_token.get("uid")

    if not firebase_uid:
        raise authentication_error()

    # -----------------------------------------------------
    # REQUIRE PHONE AUTH
    # -----------------------------------------------------

    firebase_claims = decoded_token.get(
        "firebase",
        {}
    )

    sign_in_provider = firebase_claims.get(
        "sign_in_provider"
    )

    if sign_in_provider != "phone":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phone-number authentication is required.",
        )

    # Firebase ID tokens can contain the verified phone
    # number for phone-auth users.
    phone_number = decoded_token.get(
        "phone_number"
    )

    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No verified phone number was found "
                "in the Firebase token."
            ),
        )

    # -----------------------------------------------------
    # FIND USER BY FIREBASE UID
    # -----------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.firebase_uid == firebase_uid
        )
    )

    if user is not None:

        # Firebase remains the source of truth for the
        # verified phone number.
        if user.phone_e164 != phone_number:
            # Changing the verified Firebase number invalidates all WhatsApp
            # access and pending codes tied to the previous phone.
            invalidate_link_on_phone_change(db, user)
            user.phone_e164 = phone_number

            try:
                db.commit()
                db.refresh(user)

            except IntegrityError:
                db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This phone number is already "
                        "associated with another account."
                    ),
                )

        return user

    # -----------------------------------------------------
    # USER MAY ALREADY EXIST BY PHONE NUMBER
    #
    # Useful if we ever migrate an existing local user
    # into Firebase authentication.
    # -----------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.phone_e164 == phone_number
        )
    )

    if user is not None:
        user.firebase_uid = firebase_uid

        try:
            db.commit()
            db.refresh(user)

        except IntegrityError:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to link Firebase account.",
            )

        return user

    # -----------------------------------------------------
    # FIRST LOGIN
    #
    # Automatically create our application user.
    # -----------------------------------------------------

    user = User(
        firebase_uid=firebase_uid,
        phone_e164=phone_number,
        name=None,
        preferred_language="en",
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create user account.",
        )

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
