"""add lca_params columns and migrate BatteryType.chemistry to Text

Revision ID: a1b2c3d4e5f6
Revises: 209ed4566e73
Create Date: 2026-03-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "209ed4566e73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "VehicleType", sa.Column("lca_params", postgresql.JSONB(), nullable=True)  # type: ignore[no-untyped-call]
    )
    op.add_column(
        "BatteryType", sa.Column("lca_params", postgresql.JSONB(), nullable=True)  # type: ignore[no-untyped-call]
    )
    op.add_column(
        "ChargingPointType", sa.Column("lca_params", postgresql.JSONB(), nullable=True)  # type: ignore[no-untyped-call]
    )

    # Migrate BatteryType.chemistry: JSONB -> Text
    op.add_column("BatteryType", sa.Column("chemistry_new", sa.Text(), nullable=True))
    op.execute('UPDATE "BatteryType" SET chemistry_new = chemistry::text')
    op.drop_column("BatteryType", "chemistry")
    op.alter_column("BatteryType", "chemistry_new", new_column_name="chemistry")


def downgrade() -> None:
    # Reverse chemistry migration: Text -> JSONB
    op.add_column(
        "BatteryType", sa.Column("chemistry_old", postgresql.JSONB(), nullable=True)  # type: ignore[no-untyped-call]
    )
    op.execute('UPDATE "BatteryType" SET chemistry_old = to_jsonb(chemistry)')
    op.drop_column("BatteryType", "chemistry")
    op.alter_column("BatteryType", "chemistry_old", new_column_name="chemistry")

    op.drop_column("ChargingPointType", "lca_params")
    op.drop_column("BatteryType", "lca_params")
    op.drop_column("VehicleType", "lca_params")
