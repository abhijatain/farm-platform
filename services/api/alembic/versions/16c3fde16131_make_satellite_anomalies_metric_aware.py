"""make satellite anomalies metric aware

Revision ID: 16c3fde16131
Revises: b7a64648c0f5
Create Date: 2026-10-11 15:47:48.816551

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16c3fde16131"
down_revision: Union[str, Sequence[str], None] = "b7a64648c0f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make satellite anomalies metric-aware."""

    # ---------------------------------------------------------
    # 1. Remove the old uniqueness rule:
    #
    # observation + zone_index
    #
    # That worked only while anomalies were NDVI-only.
    # ---------------------------------------------------------

    op.drop_constraint(
        "uq_satellite_anomaly_observation_zone",
        "satellite_anomalies",
        type_="unique",
    )

    # ---------------------------------------------------------
    # 2. Store both the minimum and maximum value of each zone.
    #
    # zone_min_value was enough for low-NDVI anomalies.
    # For high anomalies such as BSI, zone_max_value is useful.
    #
    # nullable=True preserves all existing anomaly rows.
    # ---------------------------------------------------------

    op.add_column(
        "satellite_anomalies",
        sa.Column(
            "zone_max_value",
            sa.Float(),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # 3. New uniqueness rule:
    #
    # observation + metric + zone_index
    #
    # This allows:
    #
    # observation A / ndvi / zone 1
    # observation A / ndmi / zone 1
    # observation A / bsi  / zone 1
    # ---------------------------------------------------------

    op.create_unique_constraint(
        "uq_satellite_anomalies_observation_metric_zone",
        "satellite_anomalies",
        [
            "satellite_observation_id",
            "index_type",
            "zone_index",
        ],
    )

    # ---------------------------------------------------------
    # 4. Speed up the API query used by 8H:
    #
    # WHERE satellite_observation_id = ...
    # AND index_type = ...
    # ---------------------------------------------------------

    op.create_index(
        "ix_satellite_anomalies_observation_metric",
        "satellite_anomalies",
        [
            "satellite_observation_id",
            "index_type",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Return to the old NDVI-only anomaly schema."""

    op.drop_index(
        "ix_satellite_anomalies_observation_metric",
        table_name="satellite_anomalies",
    )

    op.drop_constraint(
        "uq_satellite_anomalies_observation_metric_zone",
        "satellite_anomalies",
        type_="unique",
    )

    op.drop_column(
        "satellite_anomalies",
        "zone_max_value",
    )

    op.create_unique_constraint(
        "uq_satellite_anomaly_observation_zone",
        "satellite_anomalies",
        [
            "satellite_observation_id",
            "zone_index",
        ],
    )
