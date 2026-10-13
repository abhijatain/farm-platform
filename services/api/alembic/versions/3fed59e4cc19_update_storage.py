"""update  storage

Revision ID: 3fed59e4cc19
Revises: f23f184a9afa
Create Date: 2026-10-13 15:02:31.250087

"""

from __future__ import annotations

import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3fed59e4cc19"
down_revision: Union[str, Sequence[str], None] = "f23f184a9afa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(
    value: str,
    fallback: str,
) -> str:
    normalized = unicodedata.normalize("NFKD", value)

    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        ascii_value,
    ).strip("-")

    if not slug:
        slug = fallback

    return slug[:60].strip("-") or fallback


def upgrade() -> None:
    op.add_column(
        "farms",
        sa.Column(
            "storage_slug",
            sa.String(length=80),
            nullable=True,
        ),
    )

    op.add_column(
        "fields",
        sa.Column(
            "storage_slug",
            sa.String(length=80),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    for row in connection.execute(sa.text("SELECT id, name FROM farms")).mappings():
        connection.execute(
            sa.text(
                """
                UPDATE farms
                SET storage_slug = :slug
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "slug": _slugify(
                    str(row["name"]),
                    "farm",
                ),
            },
        )

    for row in connection.execute(sa.text("SELECT id, name FROM fields")).mappings():
        connection.execute(
            sa.text(
                """
                UPDATE fields
                SET storage_slug = :slug
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "slug": _slugify(
                    str(row["name"]),
                    "field",
                ),
            },
        )

    op.alter_column(
        "farms",
        "storage_slug",
        existing_type=sa.String(length=80),
        nullable=False,
    )

    op.alter_column(
        "fields",
        "storage_slug",
        existing_type=sa.String(length=80),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column(
        "fields",
        "storage_slug",
    )

    op.drop_column(
        "farms",
        "storage_slug",
    )
