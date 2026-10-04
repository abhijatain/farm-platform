import firebase_admin
from firebase_admin import credentials

from app.core.config import settings


def get_firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()

    except ValueError:
        # Local / Raspberry Pi development
        if settings.firebase_credentials_path is not None:
            credential_path = settings.firebase_credentials_path

            if not credential_path.exists():
                raise RuntimeError(
                    f"Firebase credentials file not found: "
                    f"{credential_path}"
                )

            cred = credentials.Certificate(
                str(credential_path)
            )

            return firebase_admin.initialize_app(
                cred,
                options={
                    "projectId": settings.firebase_project_id,
                },
            )

        # Later on Cloud Run, Application Default
        # Credentials can be used automatically.
        return firebase_admin.initialize_app(
            options={
                "projectId": settings.firebase_project_id,
            }
        )
