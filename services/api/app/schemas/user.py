from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID

    phone_e164: str
    name: str | None
    preferred_language: str

    created_at: datetime
    updated_at: datetime
