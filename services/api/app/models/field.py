
from __future__ import annotations

from uuid import UUID

from geoalchemy2 import Geometry
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


class Field(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fields"

    farm_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "farms.id",
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

    boundary: Mapped[object] = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )

    farm: Mapped["Farm"] = relationship(
        back_populates="fields",
    )

    crop_cycles: Mapped[list["CropCycle"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
    )

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
    )

    satellite_observations: Mapped[list["SatelliteObservation"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
        order_by=("SatelliteObservation.observed_on"),
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
                fallback="field",
            )

        return value
