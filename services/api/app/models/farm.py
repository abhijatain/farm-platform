
from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.storage_slug import make_storage_slug


class Farm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "farms"

    owner_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    storage_slug: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    location_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    owner: Mapped["User"] = relationship(
        back_populates="farms",
    )

    fields: Mapped[list["Field"]] = relationship(
        back_populates="farm",
        cascade="all, delete-orphan",
    )

    seasons: Mapped[list["Season"]] = relationship(
        back_populates="farm",
        cascade="all, delete-orphan",
    )

    @validates("name")
    def _set_storage_slug_once(
        self,
        key: str,
        value: str,
    ) -> str:
        if not getattr(
            self,
            "storage_slug",
            None,
        ):
            self.storage_slug = make_storage_slug(
                value,
                fallback="farm",
            )

        return value
