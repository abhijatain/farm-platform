from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    firebase_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    phone_e164: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )

    farms: Mapped[list["Farm"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
