"""Initialize Firebase token verification for HTTP authentication."""

from pathlib import Path

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings


def get_firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()

    except ValueError:
        pass

    credentials_path = settings.firebase_credentials_path

    if credentials_path is not None:
        credentials_path = Path(credentials_path).expanduser().resolve()

        if not credentials_path.exists():
            raise RuntimeError(
                "Firebase service account file does not exist: " f"{credentials_path}"
            )

        credential = credentials.Certificate(str(credentials_path))

        return firebase_admin.initialize_app(
            credential,
            {
                "projectId": settings.firebase_project_id,
            },
        )

    # Later on Cloud Run we can use
    # Application Default Credentials.
    return firebase_admin.initialize_app(
        options={
            "projectId": settings.firebase_project_id,
        }
    )


firebase_app = get_firebase_app()
